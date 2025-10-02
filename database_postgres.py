#!/usr/bin/env python3
"""
Base de datos PostgreSQL para API Keys del servidor DNI detallado
"""
import psycopg2
import os
from datetime import datetime, timedelta

# URL de conexión a PostgreSQL de Railway
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:KtvWiXujOvJYKfgJPMHxGntBaDYHPAXg@yamabiko.proxy.rlwy.net:27118/railway')

def init_database():
    """Inicializa la base de datos PostgreSQL"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Crear tabla para API Keys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT DEFAULT '',
                last_used TIMESTAMP NULL,
                usage_count INTEGER DEFAULT 0,
                created_by TEXT DEFAULT '',
                time_remaining INTEGER DEFAULT 0
            )
        ''')
        
        # Crear índices
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_api_keys_expires 
            ON api_keys(expires_at)
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Base de datos PostgreSQL inicializada")
        
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")

def validate_api_key(api_key):
    """
    Valida una API Key
    
    Args:
        api_key (str): La API Key a validar
        
    Returns:
        dict: Resultado de la validación
    """
    if not api_key:
        return {
            'valid': False,
            'error': '🚫 ¡Ey! ¿Dónde está tu API Key? No puedes entrar sin ella. Contacta a @zGatoO - @WinniePoohOFC - @choco_tete para conseguir una'
        }
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Buscar la API Key
        cursor.execute('''
            SELECT key, expires_at, created_at, description, usage_count, created_by, time_remaining
            FROM api_keys 
            WHERE key = %s
        ''', (api_key,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {
                'valid': False,
                'error': '🤡 ¿En serio? Esa API Key no existe ni en mis sueños más locos. Contacta a @zGatoO - @WinniePoohOFC - @choco_tete para que te den una de verdad'
            }
        
        key, expires_at, created_at, description, usage_count, created_by, time_remaining = row
        
        # Calcular tiempo restante real basado en la fecha de expiración
        expires_dt = datetime.fromisoformat(expires_at.isoformat())
        now = datetime.now()
        real_time_remaining = int((expires_dt - now).total_seconds())
        
        # Verificar si ha expirado
        if real_time_remaining <= 0:
            conn.close()
            return {
                'valid': False,
                'error': '⏰ ¡Ups! Tu API Key ya se fue de vacaciones. Contacta a @zGatoO - @WinniePoohOFC - @choco_tete para renovarla (y no seas tan lento la próxima vez)'
            }
        
        # Actualizar tiempo restante en la base de datos (sin restar por uso)
        new_time_remaining = real_time_remaining
        
        # Actualizar uso y tiempo restante
        cursor.execute('''
            UPDATE api_keys 
            SET last_used = CURRENT_TIMESTAMP, usage_count = usage_count + 1, time_remaining = %s
            WHERE key = %s
        ''', (new_time_remaining, api_key))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'valid': True,
            'expires_at': expires_at.isoformat(),
            'created_at': created_at.isoformat(),
            'description': description,
            'usage_count': usage_count + 1,
            'created_by': created_by,
            'time_remaining': new_time_remaining
        }
        
    except Exception as e:
        print(f"Error validando API Key: {e}")
        return {
            'valid': False,
            'error': f'Error interno: {str(e)}'
        }

def register_api_key(api_key, description, expires_at, created_by="admin"):
    """Registra una API Key desde el panel de administración"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Calcular tiempo restante en segundos
        expires_dt = datetime.fromisoformat(expires_at)
        now = datetime.now()
        time_remaining = int((expires_dt - now).total_seconds())
        
        # Insertar o actualizar la API Key
        cursor.execute('''
            INSERT INTO api_keys (key, description, expires_at, created_at, created_by, time_remaining)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO UPDATE SET
                description = EXCLUDED.description,
                expires_at = EXCLUDED.expires_at,
                created_by = EXCLUDED.created_by,
                time_remaining = EXCLUDED.time_remaining
        ''', (api_key, description, expires_at, datetime.now().isoformat(), created_by, time_remaining))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error registrando API Key: {e}")
        return False

def delete_api_key(api_key, requesting_user):
    """Elimina una API Key desde el panel de administración (solo el creador)"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Verificar que el usuario sea el creador
        cursor.execute('SELECT created_by FROM api_keys WHERE key = %s', (api_key,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False, "API Key no encontrada"
        
        created_by = row[0]
        if created_by != requesting_user:
            conn.close()
            return False, "Solo el creador puede eliminar esta API Key"
        
        # Eliminar la API Key
        cursor.execute('DELETE FROM api_keys WHERE key = %s', (api_key,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "API Key eliminada correctamente"
        
    except Exception as e:
        print(f"Error eliminando API Key: {e}")
        return False, f"Error: {str(e)}"
