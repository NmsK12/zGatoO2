#!/usr/bin/env python3
"""
Generador de API Keys para el servidor DNI detallado
"""
import argparse
import sys
from database import create_api_key, list_api_keys, revoke_api_key, init_database

def main():
    parser = argparse.ArgumentParser(description='Generador de API Keys - DNI Detallado')
    parser.add_argument('minutes', type=int, nargs='?', default=60,
                       help='Minutos de validez (default: 60)')
    parser.add_argument('--description', '-d', type=str, default='',
                       help='Descripcion de la API Key')
    parser.add_argument('--list', '-l', action='store_true',
                       help='Listar API Keys existentes')
    parser.add_argument('--revoke', '-r', type=str,
                       help='Revocar API Key especifica')
    
    args = parser.parse_args()
    
    # Inicializar base de datos
    init_database()
    
    if args.list:
        print("API Keys existentes para DNI Detallado:")
        print("-" * 60)
        
        rows = list_api_keys()
        
        if not rows:
            print("No hay API Keys en la base de datos")
            return
        
        for row in rows:
            key, created, expires, desc, usage, status = row
            print(f"Key: {key[:8]}...{key[-8:]}")
            print(f"Estado: {status}")
            print(f"Creada: {created}")
            print(f"Expira: {expires}")
            print(f"Descripcion: {desc or 'Sin descripcion'}")
            print(f"Usos: {usage}")
            print("-" * 60)
        return
    
    if args.revoke:
        if revoke_api_key(args.revoke):
            print(f"API Key {args.revoke[:8]}...{args.revoke[-8:]} revocada exitosamente")
        else:
            print(f"API Key {args.revoke[:8]}...{args.revoke[-8:]} no encontrada")
        return
    
    # Crear nueva API Key
    print(f"Generando API Key para DNI Detallado - Valida por {args.minutes} minutos...")
    
    key, expires = create_api_key(args.minutes, args.description)
    
    if key:
        print(f"Nueva API Key: {key}")
        print(f"Expira en: {expires}")
        print(f"Descripcion: {args.description or 'Sin descripcion'}")
        print(f"\nUsar en: https://tu-dnit-api.up.railway.app/dnit?dni=12345678&key={key}")
    else:
        print("Error generando API Key")

if __name__ == "__main__":
    main()
