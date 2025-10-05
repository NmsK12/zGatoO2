#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API DNI Detallado - WolfData Dox
Servidor especializado para consultas detalladas de DNI con 4 imágenes
"""

import asyncio
import base64
import json
import logging
import os
import re
import time
import threading
import uuid
from datetime import datetime, timedelta
from io import BytesIO

from flask import Flask, jsonify, request, send_file, make_response
from PIL import Image
from database_postgres import validate_api_key, init_database, register_api_key, delete_api_key
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import MessageMediaPhoto

import config

# Base64 del logo de OlimpoDataBot que queremos filtrar
OLIMPO_LOGO_BASE64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAQDAwQDAwQEAwQFBAQFBgoHBgYGBg0JCggKDw0QEA8NDw4RExgUERIXEg4PFRwVFxkZGxsbEBQdHx0aHxgaGxr/2wBDAQQFBQYFBgwHBwwaEQ8RGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhr/wgARCAQABAADASIAAhEBAxEB/8QAHAAAAAcBAQAAAAAAAAAAAAAAAAECBAUGBwMI/8QAGwEAAQUBAQAAAAAAAAAAAAAAAQACAwQFBgf/2gAMAwEAAhADEAAAAcgHI54+pcwitKQAsICKjQAlhARWfM0ugQCFEQBWEBBYQEVnzUB0HMylhAS6K5Gk7SRMso6te6j7cOzcSqVzN9aXjpGMg1DCBPlqlYmXg0YpXJU+f0HMBdVcDB7DkAepoCS1cwj0LmSHUcyJ6nxNDqfE0uym4ScFxSF2TyBXUuRJLHI0uo5BLqnmSHUcySWEEQskEkaSJJY5ghcnFS0OhHESZ85ZJJGXiZWJh0FBJTZzzl05ssc+nLq6McercOUkidCYSElnzCPUuYCWSQUARJEpISUEghZJCSz5hLqOZIdBzAJgjIAASAARAMkgAAADJIGQRUAEgCCBgAOAAICkmkYASMEaRmlSTlKkx2eHbj3LOjZ20ZKZkJK01Ey8RBqJCVWMs5mEm4NKHNJz5pgjaQAE5QI0DNCgVGkJGQCRECSUEmkojNIGkIqIgkREEDBEiAAgZAkCMgiYAKABIBKkoJBhJIMkhKxUrFdjkmU9FJGFJLxUvDV7gAKxnO0qQyzx6c1uiU2cNgiIyfEAQBMEZSiBIAAkgASAACIACABgkgAAAAiAAgRgOQAAJGRpAAJAEYAACIBGgDI0gAEjACIACQMBIAwURgwjCTSdpWUVxv34ODG4YycWyUACWpOw03B1tdII7WQc1DTtfSgzJU1EgAmmYCIA"

def is_olimpo_logo(image_base64):
    """Verifica si una imagen es el logo de OlimpoDataBot"""
    try:
        # Solo filtrar si es exactamente el logo conocido
        if image_base64.startswith(OLIMPO_LOGO_BASE64[:200]):
            return True
        
        # Verificar tamaño muy pequeño (probablemente logo) - ser más permisivo
        if len(image_base64) < 3000:  # Solo imágenes muy pequeñas
            return True
            
        return False
    except Exception:
        return False

def detect_image_type(image_base64, current_count):
    """Detecta el tipo de imagen basándose en el contenido y orden."""
    try:
        # Decodificar la imagen
        image_data = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_data))
        
        # Convertir a RGB si es necesario
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Obtener dimensiones
        width, height = image.size
        aspect_ratio = width / height
        
        logger.info(f"Analizando imagen: {width}x{height}, aspect_ratio: {aspect_ratio:.2f}, current_count: {current_count}")
        
        # Imagen de cara: suele ser más alta que ancha (retrato) o casi cuadrada pero grande
        if (aspect_ratio < 0.95 and height > 150) or (0.9 <= aspect_ratio <= 1.1 and height > 180):
            logger.info("Detectado como CARA (retrato o cuadrada grande)")
            return 'CARA'
        
        # Imagen de firma: suele ser más ancha que alta (paisaje) y más pequeña
        elif aspect_ratio > 1.3 and width < 500:
            logger.info("Detectado como FIRMA (paisaje, ancha)")
            return 'FIRMA'
        
        # Imagen de huellas: suele ser más cuadrada o ligeramente rectangular pero más pequeña
        elif 0.8 <= aspect_ratio <= 1.2 and height <= 200:
            logger.info("Detectado como HUELLAS (cuadrada pequeña)")
            return 'HUELLAS'
        
        # Por defecto, basarse en el orden si no se puede determinar
        else:
            if current_count == 0:
                logger.info("Fallback: CARA (primera imagen)")
                return 'CARA'
            elif current_count == 1:
                logger.info("Fallback: FIRMA (segunda imagen)")
                return 'FIRMA'
            else:
                logger.info("Fallback: HUELLAS (imagen adicional)")
                return 'HUELLAS'
                
    except Exception as e:
        logger.error(f"Error detectando tipo de imagen: {e}")
        # Fallback basado en el orden
        if current_count == 0:
            return 'CARA'
        elif current_count == 1:
            return 'FIRMA'
        else:
            return 'HUELLAS'

def create_request_id():
    """Crea un request_id único"""
    return str(uuid.uuid4())[:8].upper()

def check_connection():
    """Verifica si el cliente de Telegram está conectado y reconecta si es necesario."""
    global client, loop
    
    try:
        if not client or not client.is_connected():
            logger.warning("Cliente de Telegram desconectado, intentando reconectar...")
            restart_telethon()
            time.sleep(3)  # Esperar a que se reconecte
            return client and client.is_connected()
        return True
    except Exception as e:
        logger.error(f"Error verificando conexión: {str(e)}")
        return False

def register_pending_request(request_id, future):
    """Registra una consulta pendiente"""
    with request_lock:
        pending_requests[request_id] = {
            'future': future,
            'created_at': time.time(),
            'dni': None,
            'data': None
        }
        logger.info(f"Request {request_id} registrado. Total pendientes: {len(pending_requests)}")

def complete_request(request_id, data):
    """Completa una consulta pendiente"""
    with request_lock:
        if request_id in pending_requests:
            pending_requests[request_id]['data'] = data
            pending_requests[request_id]['future'].set_result(data)
            del pending_requests[request_id]
            logger.info(f"Request {request_id} completado. Pendientes restantes: {len(pending_requests)}")
            return True
        return False

def cleanup_expired_requests():
    """Limpia consultas expiradas (más de 60 segundos)"""
    current_time = time.time()
    with request_lock:
        expired_requests = []
        for request_id, request_data in pending_requests.items():
            if current_time - request_data['created_at'] > 60:
                expired_requests.append(request_id)
        
        for request_id in expired_requests:
            if request_id in pending_requests:
                pending_requests[request_id]['future'].set_exception(Exception("Request expirado"))
                del pending_requests[request_id]
                logger.warning(f"Request {request_id} expirado y eliminado")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables globales
client = None
loop = None
is_ready = False  # Flag global para saber si el bot ya está listo

# Sistema de request_id para evitar mezcla de datos
pending_requests = {}  # Diccionario de consultas pendientes
request_lock = threading.Lock()  # Lock para acceso thread-safe

def parse_dnit_response(text):
    """Parsea la respuesta del bot para extraer datos detallados del DNI (comando /dnit)."""
    data = {}
    
    # Limpiar el texto de caracteres especiales
    clean_text = text.replace('**', '').replace('`', '').replace('*', '')
    
    # Información básica
    dni_match = re.search(r'DNI\s*[➾\-=]\s*(\d+)', clean_text)
    if dni_match:
        data['DNI'] = dni_match.group(1)
    
    nombres_match = re.search(r'NOMBRES\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if nombres_match:
        data['NOMBRES'] = nombres_match.group(1).strip()
    
    apellidos_match = re.search(r'APELLIDOS\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if apellidos_match:
        data['APELLIDOS'] = apellidos_match.group(1).strip()
    
    genero_match = re.search(r'GENERO\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if genero_match:
        data['GENERO'] = genero_match.group(1).strip()
    
    # Información de nacimiento
    fecha_nacimiento_match = re.search(r'FECHA NACIMIENTO\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if fecha_nacimiento_match:
        data['FECHA_NACIMIENTO'] = fecha_nacimiento_match.group(1).strip()
    
    edad_match = re.search(r'EDAD\s*[➾\-=]\s*(\d+)\s*AÑOS?', clean_text)
    if edad_match:
        data['EDAD'] = f"{edad_match.group(1)} AÑOS"
    
    departamento_match = re.search(r'DEPARTAMENTO\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if departamento_match:
        data['DEPARTAMENTO'] = departamento_match.group(1).strip()
    
    provincia_match = re.search(r'PROVINCIA\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if provincia_match:
        data['PROVINCIA'] = provincia_match.group(1).strip()
    
    distrito_match = re.search(r'DISTRITO\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if distrito_match:
        data['DISTRITO'] = distrito_match.group(1).strip()
    
    # Información general
    nivel_educativo_match = re.search(r'NIVEL EDUCATIVO\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if nivel_educativo_match:
        data['NIVEL_EDUCATIVO'] = nivel_educativo_match.group(1).strip()
    
    estado_civil_match = re.search(r'ESTADO CIVIL\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if estado_civil_match:
        data['ESTADO_CIVIL'] = estado_civil_match.group(1).strip()
    
    estatura_match = re.search(r'ESTATURA\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if estatura_match:
        data['ESTATURA'] = estatura_match.group(1).strip()
    
    fecha_inscripcion_match = re.search(r'FECHA INSCRIPCION\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if fecha_inscripcion_match:
        data['FECHA_INSCRIPCION'] = fecha_inscripcion_match.group(1).strip()
    
    fecha_emision_match = re.search(r'FECHA EMISION\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if fecha_emision_match:
        data['FECHA_EMISION'] = fecha_emision_match.group(1).strip()
    
    fecha_caducidad_match = re.search(r'FECHA CADUCIDAD\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if fecha_caducidad_match:
        data['FECHA_CADUCIDAD'] = fecha_caducidad_match.group(1).strip()
    
    donante_organos_match = re.search(r'DONANTE ORGANOS\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if donante_organos_match:
        data['DONANTE_ORGANOS'] = donante_organos_match.group(1).strip()
    
    padre_match = re.search(r'PADRE\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if padre_match:
        data['PADRE'] = padre_match.group(1).strip()
    
    madre_match = re.search(r'MADRE\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if madre_match:
        data['MADRE'] = madre_match.group(1).strip()
    
    restriccion_match = re.search(r'RESTRICCION\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if restriccion_match:
        data['RESTRICCION'] = restriccion_match.group(1).strip()
    
    # Domicilio
    direccion_match = re.search(r'DIRECCION\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if direccion_match:
        data['DIRECCION'] = direccion_match.group(1).strip()
    
    # Ubigeos
    ubigeo_reneic_match = re.search(r'UBIGEO RENIEC\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if ubigeo_reneic_match:
        data['UBIGEO_RENIEC'] = ubigeo_reneic_match.group(1).strip()
    
    ubigeo_ine_match = re.search(r'UBIGEO INE\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if ubigeo_ine_match:
        data['UBIGEO_INE'] = ubigeo_ine_match.group(1).strip()
    
    ubigeo_sunat_match = re.search(r'UBIGEO SUNAT\s*[➾\-=]\s*([^\n\r]+)', clean_text)
    if ubigeo_sunat_match:
        data['UBIGEO_SUNAT'] = ubigeo_sunat_match.group(1).strip()
    
    return data

def consult_dnit_sync(dni_number):
    """Consulta el DNI detallado usando Telethon de forma síncrona con request_id único."""
    global client, loop, is_ready
    
    # Verificar que el cliente esté disponible y listo
    if not is_ready or not client or not loop:
        logger.error("Cliente de Telethon no está disponible o no está listo")
        return {
            'success': False,
            'error': 'Cliente de Telegram no disponible. Intenta nuevamente en unos segundos.'
        }
    
    # Verificar conexión
    if not client.is_connected():
        logger.warning("Cliente desconectado, esperando reconexión automática...")
        return {
            'success': False,
            'error': 'Cliente de Telegram desconectado. Intenta nuevamente en unos segundos.'
        }
    
    # Crear request_id único
    request_id = create_request_id()
    
    try:
        # Limpiar consultas expiradas
        cleanup_expired_requests()
        
        # Ejecutar la consulta asíncrona en el loop existente
        future = asyncio.run_coroutine_threadsafe(consult_dnit_async(dni_number, request_id), loop)
        
        # Esperar resultado con timeout
        result = future.result(timeout=35)  # 35 segundos de timeout
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"Timeout consultando DNI detallado {dni_number} (request_id {request_id})")
        return {
            'success': False,
            'error': 'Timeout: No se recibió respuesta en 35 segundos',
            'request_id': request_id
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error consultando DNI detallado {dni_number} (request_id {request_id}): {error_msg}")
        
        # Si es error de desconexión, intentar reconectar
        if "disconnected" in error_msg.lower() or "connection" in error_msg.lower():
            logger.info("Error de desconexión detectado, intentando reconectar...")
            try:
                restart_telethon()
                # Esperar un poco para que se reconecte
                time.sleep(3)
                # Intentar la consulta nuevamente con nuevo request_id
                new_request_id = create_request_id()
                new_future = asyncio.run_coroutine_threadsafe(consult_dnit_async(dni_number, new_request_id), loop)
                result = new_future.result(timeout=35)
                return result
            except Exception as retry_error:
                logger.error(f"Error en reintento: {str(retry_error)}")
        
        return {
            'success': False,
            'error': f'Error en la consulta: {error_msg}'
        }

async def consult_dnit_async(dni_number, request_id):
    """Consulta asíncrona del DNI detallado con sistema de request_id único."""
    global client
    
    try:
        logger.info(f"Iniciando consulta DNI detallado {dni_number} con request_id {request_id}")
        
        # Enviar comando /dnit normal (sin request_id visible)
        command = f"/dnit {dni_number}"
        await client.send_message(config.TARGET_BOT, command)
        logger.info(f"Comando enviado: {command} (request_id interno: {request_id})")
        
        # Esperar respuesta con timeout de 30 segundos
        start_time = time.time()
        timeout = 30
        command_time = start_time
        
        while time.time() - start_time < timeout:
            # Obtener mensajes recientes
            messages = await client.get_messages(config.TARGET_BOT, limit=10)
            current_timestamp = time.time()
            
            # Buscar respuesta específica para nuestro DNI
            for message in messages:
                # Solo mensajes posteriores a nuestro comando
                if message.date.timestamp() > command_time:
                    logger.info(f"[{request_id}] Revisando mensaje: {message.text[:100]}... (from_id: {message.from_id})")
                    
                    # Verificar que sea del bot
                    is_from_bot = (
                        (message.from_id and str(message.from_id) == config.TARGET_BOT_ID) or
                        message.from_id is None
                    )
                    
                    if is_from_bot and message.text:
                        # Buscar respuesta para nuestro DNI específico (más flexible)
                        if (f"DNI ➾ {dni_number}" in message.text or 
                            f"DNI ➾ {dni_number} -" in message.text or
                            f"DNI ➾ {dni_number} |" in message.text or
                            str(dni_number) in message.text):
                            logger.info(f"¡Respuesta encontrada para request_id {request_id}!")
                            
                            # Procesar respuesta
                            text_data = message.text
                            images = []
                            
                            # Verificar si hay imágenes adjuntas
                            if message.media and hasattr(message.media, 'photo'):
                                logger.info("Descargando imagen principal...")
                                image_bytes = await client.download_media(message.media, file=BytesIO())
                                image_base64 = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
                                
                                # Filtrar el logo de OlimpoDataBot
                                if not is_olimpo_logo(image_base64):
                                    # Determinar tipo de imagen basado en el contenido real
                                    img_type = detect_image_type(image_base64, len(images))
                                    
                                    images.append({
                                        'type': img_type,
                                        'base64': image_base64
                                    })
                                    logger.info(f"Imagen {img_type} descargada: {len(image_base64)} caracteres")
                                else:
                                    logger.info("Logo de OlimpoDataBot detectado - ignorando imagen principal")
                            
                            # Usar iter_messages para capturar TODAS las imágenes nuevas
                            logger.info("Capturando todas las imágenes usando iter_messages...")
                            
                            # Marca de tiempo para capturar solo mensajes nuevos
                            capture_start_time = time.time()
                            max_capture_time = 6  # 6 segundos para capturar todas las imágenes
                            processed_image_ids = set()
                            
                            try:
                                # Usar iter_messages para obtener mensajes en tiempo real
                                async for msg in client.iter_messages(config.TARGET_BOT, limit=50):
                                    # Solo procesar si no hemos excedido el tiempo
                                    if (time.time() - capture_start_time) > max_capture_time:
                                        break
                                    
                                    # Solo mensajes posteriores a nuestro comando y con imágenes
                                    if (msg.date.timestamp() > command_time and 
                                        msg.id not in processed_image_ids and
                                        msg.media and hasattr(msg.media, 'photo')):
                                        
                                        logger.info("Descargando imagen capturada con iter_messages...")
                                        image_bytes = await client.download_media(msg.media, file=BytesIO())
                                        image_base64 = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
                                        
                                        # Filtrar el logo de OlimpoDataBot
                                        if not is_olimpo_logo(image_base64):
                                            # Determinar tipo de imagen basado en el contenido real
                                            img_type = detect_image_type(image_base64, len(images))
                                            
                                            images.append({
                                                'type': img_type,
                                                'base64': image_base64
                                            })
                                            processed_image_ids.add(msg.id)
                                            logger.info(f"Imagen {img_type} capturada: {len(image_base64)} caracteres")
                                        else:
                                            logger.info("Logo de OlimpoDataBot detectado - ignorando")
                                            processed_image_ids.add(msg.id)
                                    
                                    # Si ya tenemos 4 imágenes, salir
                                    if len(images) >= 4:
                                        logger.info("¡4 imágenes capturadas! Terminando búsqueda.")
                                        break
                                    
                                    # Pequeña pausa para no sobrecargar
                                    await asyncio.sleep(0.1)
                                    
                            except Exception as e:
                                logger.error(f"Error en iter_messages: {e}")
                            
                            logger.info(f"Captura completada. Total imágenes: {len(images)}")
                            
                            parsed_data = parse_dnit_response(text_data)
                            
                            result = {
                                'success': True,
                                'text_data': text_data,
                                'images': images,
                                'parsed_data': parsed_data,
                                'request_id': request_id
                            }
                            
                            # Retornar resultado directamente
                            return result
            
            # Esperar un poco antes de revisar nuevamente
            await asyncio.sleep(1)
        
        # Timeout
        logger.error(f"Timeout para request_id {request_id} - DNI {dni_number}")
        error_result = {
            'success': False,
            'error': 'Timeout: No se recibió respuesta en 30 segundos',
            'request_id': request_id
        }
        return error_result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error consultando DNI detallado {dni_number} (request_id {request_id}): {error_msg}")
        
        error_result = {
            'success': False,
            'error': f'Error en la consulta: {error_msg}',
            'request_id': request_id
        }
        return error_result

# Crear la aplicación Flask
app = Flask(__name__)

# Inicializar base de datos
init_database()

@app.route('/', methods=['GET'])
def home():
    """Página principal con información del servidor."""
    with request_lock:
        pending_count = len(pending_requests)
    
    return jsonify({
        'servicio': 'API DNI Detallado',
        'comando': '/dnit?dni=12345678&key=TU_API_KEY',
        'sistema': 'Request ID único para evitar mezcla de datos',
        'consultas_pendientes': pending_count,
        'endpoints': {
            'consulta': '/dnit?dni=12345678&key=TU_API_KEY',
            'estado': '/status',
            'salud': '/health'
        },
        'info': '@zGatoO - @WinniePoohOFC - @choco_tete'
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'OK',
        'service': 'DNI Detallado API',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/register-key', methods=['POST'])
def register_key():
    """Endpoint para registrar API Keys desde el panel de administración."""
    try:
        data = request.get_json()
        
        if not data or 'key' not in data:
            return jsonify({
                'success': False,
                'error': 'Datos de API Key requeridos'
            }), 400
        
        api_key = data['key']
        description = data.get('description', 'API Key desde panel')
        expires_at = data.get('expires_at', (datetime.now() + timedelta(hours=1)).isoformat())
        
        if register_api_key(api_key, description, expires_at):
            return jsonify({
                'success': True,
                'message': 'API Key registrada correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error registrando API Key'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500

@app.route('/delete-key', methods=['POST'])
def delete_key():
    """Endpoint para eliminar API Keys desde el panel de administración."""
    try:
        data = request.get_json()
        
        if not data or 'key' not in data:
            return jsonify({
                'success': False,
                'error': 'API Key requerida'
            }), 400
        
        api_key = data['key']
        
        if delete_api_key(api_key):
            return jsonify({
                'success': True,
                'message': 'API Key eliminada correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error eliminando API Key'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500

@app.route('/dnit', methods=['GET'])
def dnit_result():
    """Endpoint para consultar DNI detallado."""
    # Validar API Key
    api_key = request.args.get('key') or request.headers.get('X-API-Key')
    validation = validate_api_key(api_key)
    
    if not validation['valid']:
        return jsonify({
            'success': False,
            'error': validation['error']
        }), 401
    
    dni = request.args.get('dni')
    
    if not dni:
        return jsonify({
            'success': False,
            'error': 'Parámetro DNI requerido. Use: /dnit?dni=12345678&key=TU_API_KEY'
        }), 400
    
    # Verificar formato del DNI
    if not dni.isdigit() or len(dni) != 8:
        return jsonify({
            'success': False,
            'error': 'DNI debe ser un número de 8 dígitos'
        }), 400
    
    # Ejecutar consulta síncrona
    result = consult_dnit_sync(dni)
    
    if result['success']:
        response = {
            'success': True,
            'dni': dni,
            'timestamp': datetime.now().isoformat(),
            'data': result['parsed_data'],
            'request_id': result.get('request_id', 'N/A')
        }
        
        # Agregar imágenes si existen
        if result['images']:
            response['images'] = result['images']
        
        return jsonify(response)
    else:
        return jsonify({
            'success': False,
            'error': result['error'],
            'request_id': result.get('request_id', 'N/A')
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de salud de la API."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'WolfData DNI API - Detallado'
    })

@app.route('/status', methods=['GET'])
def status():
    """Endpoint para ver el estado de las consultas pendientes."""
    with request_lock:
        pending_count = len(pending_requests)
        pending_list = []
        for req_id, req_data in pending_requests.items():
            pending_list.append({
                'request_id': req_id,
                'dni': req_data.get('dni'),
                'created_at': req_data['created_at'],
                'age_seconds': int(time.time() - req_data['created_at'])
            })
    
    return jsonify({
        'pending_requests': pending_count,
        'requests': pending_list,
        'timestamp': datetime.now().isoformat()
    })


def restart_telethon():
    """Reinicia la conexión de Telethon."""
    global client, loop
    
    try:
        if client:
            logger.info("Cerrando cliente anterior...")
            try:
                # Cerrar cliente de forma segura
                if loop and not loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(client.disconnect(), loop)
                    try:
                        future.result(timeout=5)
                    except Exception as e:
                        logger.warning(f"Error cerrando cliente anterior: {e}")
                else:
                    logger.warning("No hay loop disponible para desconectar cliente")
            except Exception as e:
                logger.warning(f"Error cerrando cliente anterior: {e}")
            client = None
            time.sleep(2)
        
        # Reinicializar en un nuevo hilo
        init_telethon_thread()
        logger.info("Cliente de Telethon reiniciado correctamente")
            
    except Exception as e:
        logger.error(f"Error reiniciando Telethon: {str(e)}")

def init_telethon_thread():
    """Inicializa Telethon en un hilo separado con reconexión automática."""
    def run_telethon():
        global client, loop, is_ready
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            client = TelegramClient(
                'telethon_session',
                config.API_ID,
                config.API_HASH
            )
            
            async def start_telegram():
                global is_ready
                await client.start()
                is_ready = True
                logger.info("✅ Cliente de Telethon iniciado correctamente")
                
                # Lazo infinito para reconexión automática
                while True:
                    try:
                        if not client.is_connected():
                            logger.warning("⚠️ Detectada desconexión. Reconectando...")
                            try:
                                await client.connect()
                                logger.info("🔁 Reconectado correctamente")
                            except Exception as e:
                                logger.error(f"❌ Error reconectando: {e}")
                        else:
                            # Ping de keepalive si está conectado
                            try:
                                await client.send_read_acknowledge("me")
                                logger.debug("📡 Ping enviado para mantener conexión activa")
                            except Exception:
                                pass
                        await asyncio.sleep(5)  # verifica cada 5 segundos
                    except Exception as e:
                        logger.error(f"❌ Error durante reconexión automática: {e}")
                        await asyncio.sleep(10)  # espera más tiempo si hay error
            
            loop.run_until_complete(start_telegram())
            
        except Exception as e:
            logger.error(f"Error inicializando Telethon: {str(e)}")
    
    # Iniciar en hilo separado
    thread = threading.Thread(target=run_telethon, daemon=True)
    thread.start()
    
    # Esperar un poco para que se inicialice
    time.sleep(5)

def main():
    """Función principal."""
    # Inicializar Telethon en hilo separado
    init_telethon_thread()
    
    # Iniciar Flask
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Iniciando API en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()
