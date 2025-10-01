import os

# Credenciales de la API de Telegram para tu cuenta de usuario
API_ID = int(os.getenv('API_ID', '20463783'))
API_HASH = os.getenv('API_HASH', '652a0cf6932332ccf668be49bc3480f4')

# Token de tu bot puente
BOT_TOKEN = os.getenv('BOT_TOKEN', 'tu_bot_token_aqui')

# Nombre de usuario del bot al que le harás el puente
TARGET_BOT = os.getenv('TARGET_BOT', '@OlimpoDataBot')

# Lista de IDs de usuarios administradores del bot puente
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '123456789').split(',')]
