#!/usr/bin/env python3
"""
Base de datos SQLite para API Keys del servidor DNI detallado
"""
import sqlite3
import os
from datetime import datetime, timedelta

DATABASE_FILE = 'api_keys.db'

def init_database():
    """Inicializa la base de datos SQLite"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Crear tabla para API Keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT DEFAULT '',
            last_used TIMESTAMP NULL,
            usage_count INTEGER DEFAULT 0
        )
    ''')
    
    # Crear índices
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_api_keys_expires 
        ON api_keys(expires_at)
    ''')
    
    conn.commit()
    conn.close()
    print(f"Base de datos inicializada: {DATABASE_FILE}")

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
            'error': 'Falta API Key'
        }
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Buscar la API Key
        cursor.execute('''
            SELECT key, expires_at, created_at, description, usage_count
            FROM api_keys 
            WHERE key = ?
        ''', (api_key,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {
                'valid': False,
                'error': 'API Key invalida'
            }
        
        key, expires_at, created_at, description, usage_count = row
        
        # Verificar si ha expirado
        now = datetime.now()
        expires = datetime.fromisoformat(expires_at)
        
        # Asegurar que ambas fechas tengan la misma zona horaria
        if expires.tzinfo is not None:
            now = now.replace(tzinfo=expires.tzinfo)
        elif now.tzinfo is not None:
            expires = expires.replace(tzinfo=now.tzinfo)
        
        if now > expires:
            conn.close()
            return {
                'valid': False,
                'error': 'Tu acceso expiro. Escribele a @zGatoO para renovarlo.'
            }
        
        # Actualizar uso
        cursor.execute('''
            UPDATE api_keys 
            SET last_used = CURRENT_TIMESTAMP, usage_count = usage_count + 1
            WHERE key = ?
        ''', (api_key,))
        
        conn.commit()
        conn.close()
        
        return {
            'valid': True,
            'key_data': {
                'key': key,
                'expires_at': expires_at,
                'created_at': created_at,
                'description': description,
                'usage_count': usage_count + 1
            }
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error validando API Key: {str(e)}'
        }

def create_api_key(minutes=60, description=""):
    """
    Crea una nueva API Key
    
    Args:
        minutes (int): Minutos de validez
        description (str): Descripcion de la API Key
        
    Returns:
        tuple: (api_key, expires_at) o (None, None) si hay error
    """
    import secrets
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Generar key segura
        api_key = secrets.token_hex(16)
        expires_at = datetime.now() + timedelta(minutes=minutes)
        
        # Insertar en la base de datos
        cursor.execute('''
            INSERT INTO api_keys (key, expires_at, description)
            VALUES (?, ?, ?)
        ''', (api_key, expires_at.isoformat(), description))
        
        conn.commit()
        conn.close()
        
        return api_key, expires_at
        
    except Exception as e:
        print(f"Error creando API Key: {e}")
        return None, None

def list_api_keys():
    """Lista todas las API Keys"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT key, created_at, expires_at, description, usage_count,
                   CASE WHEN expires_at > datetime('now') THEN 'ACTIVA' ELSE 'EXPIRADA' END as status
            FROM api_keys 
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows
        
    except Exception as e:
        print(f"Error listando API Keys: {e}")
        return []

def revoke_api_key(api_key):
    """Revoca una API Key"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM api_keys WHERE key = ?', (api_key,))
        
        if cursor.rowcount > 0:
            conn.commit()
            conn.close()
            return True
        else:
            conn.close()
            return False
            
    except Exception as e:
        print(f"Error revocando API Key: {e}")
        return False

def register_api_key(api_key, description, expires_at):
    """Registra una API Key desde el panel de administración"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Insertar o actualizar la API Key
        cursor.execute('''
            INSERT OR REPLACE INTO api_keys (key, description, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        ''', (api_key, description, expires_at, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error registrando API Key: {e}")
        return False

def delete_api_key(api_key):
    """Elimina una API Key desde el panel de administración"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Eliminar la API Key
        cursor.execute('DELETE FROM api_keys WHERE key = ?', (api_key,))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error eliminando API Key: {e}")
        return False

if __name__ == "__main__":
    init_database()
    print("Base de datos lista!")
