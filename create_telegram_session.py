#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para crear sesión de Telegram
Ejecutar localmente para generar el archivo .session
"""

import asyncio
from telethon import TelegramClient
import config

async def create_session():
    """Crear sesión de Telegram."""
    print("Creando sesion de Telegram...")
    print(f"API ID: {config.API_ID}")
    print(f"API Hash: {config.API_HASH}")
    print(f"Target Bot: {config.TARGET_BOT}")
    
    # Crear cliente
    client = TelegramClient('telethon_session', config.API_ID, config.API_HASH)
    
    try:
        # Iniciar sesión
        await client.start()
        print("Sesion creada exitosamente!")
        print("Archivo generado: telethon_session.session")
        
        # Verificar conexión
        me = await client.get_me()
        print(f"Conectado como: {me.first_name} (@{me.username})")
        
        # Probar envío de mensaje al bot
        print(f"Probando conexion con {config.TARGET_BOT}...")
        await client.send_message(config.TARGET_BOT, "/start")
        print("Mensaje de prueba enviado exitosamente!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await client.disconnect()
        print("Cliente desconectado")

if __name__ == '__main__':
    asyncio.run(create_session())
