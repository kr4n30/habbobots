#!/usr/bin/env python3
"""
HeadlessBotManager.py — Servicio headless para gestionar bots de Habbo
Ruta: /var/www/habbobots/bot_manager/
"""

import sys
import os
import json
import logging
import sqlite3
import threading
import time
import random
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify
from flask_cors import CORS

# Añadir el directorio del bot para importar sus módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar componentes del BotManager original
try:
    import constants as const
    from bot_instance import BotInstance
    from habbo_client import HabboClientGUI
    from sso_retriever import get_sso_ticket, check_session
    import state
except ImportError as e:
    print(f"Error importando módulos del BotManager: {e}")
    print("Asegúrate de que el proyecto original está en /var/www/habbobots/")
    sys.exit(1)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DEFAULT_PORT = 5001
DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bots.db")
LOG_LEVEL = logging.INFO

# =============================================================================
# MODELOS DE DATOS
# =============================================================================

class BotGroup:
    """Grupo de bots para un cliente/servicio específico"""
    def __init__(self, name: str, user_id: Optional[int] = None, config: dict = None):
        self.name = name
        self.user_id = user_id
        self.config = config or {}
        self.bots: List[int] = []
        self.proxies: List[str] = []
        self._proxy_idx = 0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class BotAssignment:
    """Asignación de un bot a un usuario/servicio"""
    def __init__(self, bot_index: int, user_id: int, 
                 service_id: str = None, expires_at: datetime = None):
        self.bot_index = bot_index
        self.user_id = user_id
        self.service_id = service_id
        self.expires_at = expires_at
        self.assigned_at = datetime.now()
        self.active = True

# =============================================================================
# HEADLESS BOT MANAGER
# =============================================================================

class HeadlessBotManager:
    """
    Gestor headless de bots de Habbo.
    
    Características:
    - Sin GUI (solo API REST)
    - Gestión de bots por grupos
    - Asignación de bots a usuarios
    - Auto-reconexión
    - Rotación de proxies
    """
    
    def __init__(self, db_path: str = DEFAULT_DB, port: int = DEFAULT_PORT):
        self.port = port
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Estado en memoria
        self.bots: Dict[int, BotInstance] = {}
        self.groups: Dict[str, BotGroup] = {}
        self.assignments: Dict[int, BotAssignment] = {}
        self.proxy_pool: List[str] = []
        self._proxy_idx = 0
        
        # Control de hilos
        self.running = False
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Inicializar DB y cargar estado
        self._init_db()
        self._load_state()
        
        # Configurar Flask
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()
        
        self.logger.info("=" * 60)
        self.logger.info("HeadlessBotManager v2.0 iniciado")
        self.logger.info(f"Base de datos: {self.db_path}")
        self.logger.info(f"Bots cargados: {len(self.bots)}")
        self.logger.info(f"Grupos cargados: {len(self.groups)}")
        self.logger.info(f"Proxies cargados: {len(self.proxy_pool)}")
        self.logger.info("=" * 60)
    
    def _setup_logging(self):
        """Configura logging para headless mode"""
        logger = logging.getLogger("HeadlessBotManager")
        logger.setLevel(LOG_LEVEL)
        
        # Crear directorio de logs si no existe
        log_dir = "/var/log/habbo-bot-manager"
        os.makedirs(log_dir, exist_ok=True)
        
        # Handler para consola
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(console)
        
        # Handler para archivo
        file_handler = logging.FileHandler(os.path.join(log_dir, 'bot_manager.log'))
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s'
        ))
        logger.addHandler(file_handler)
        
        return logger
    
    # =========================================================================
    # BASE DE DATOS
    # =========================================================================
    
    def _init_db(self):
        """Inicializa la base de datos SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de bots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bots (
                bot_index INTEGER PRIMARY KEY AUTOINCREMENT,
                account_data TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                proxy_address TEXT DEFAULT 'DIRECT',
                group_name TEXT,
                assigned_to INTEGER,
                service_id TEXT,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de grupos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                name TEXT PRIMARY KEY,
                user_id INTEGER,
                config TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de grupo_proxies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_proxies (
                group_name TEXT,
                proxy TEXT,
                PRIMARY KEY (group_name, proxy),
                FOREIGN KEY (group_name) REFERENCES groups(name) ON DELETE CASCADE
            )
        ''')
        
        # Tabla de proxy_pool
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS proxy_pool (
                proxy TEXT PRIMARY KEY,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de assignments (historial)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_index INTEGER,
                user_id INTEGER,
                service_id TEXT,
                expires_at TEXT,
                assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (bot_index) REFERENCES bots(bot_index) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
        self.logger.info(f"Base de datos inicializada: {self.db_path}")
    
    def _load_state(self):
        """Carga el estado desde la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Cargar bots
        cursor.execute('SELECT * FROM bots')
        for row in cursor.fetchall():
            try:
                account_data = json.loads(row['account_data'])
                bot = BotInstance(account_data, row['bot_index'])
                bot.status = row['status']
                bot.proxy_address = row['proxy_address']
                self.bots[row['bot_index']] = bot

                # Si tiene asignación activa
                if row['assigned_to']:
                    expires = None
                    if row['expires_at']:
                        try:
                            expires = datetime.fromisoformat(row['expires_at'])
                        except:
                            pass
                    assignment = BotAssignment(
                        bot_index=row['bot_index'],
                        user_id=row['assigned_to'],
                        service_id=row['service_id'],
                        expires_at=expires
                    )
                    self.assignments[row['bot_index']] = assignment
                    
            except Exception as e:
                self.logger.error(f"Error cargando bot {row['index']}: {e}")
        
        # Cargar grupos
        cursor.execute('SELECT * FROM groups')
        for row in cursor.fetchall():
            group = BotGroup(
                name=row['name'],
                user_id=row['user_id'],
                config=json.loads(row['config']) if row['config'] else {}
            )
            try:
                group.created_at = datetime.fromisoformat(row['created_at'])
                group.updated_at = datetime.fromisoformat(row['updated_at'])
            except:
                pass
            
            # Cargar proxies del grupo
            cursor.execute('SELECT proxy FROM group_proxies WHERE group_name=?', (row['name'],))
            group.proxies = [r['proxy'] for r in cursor.fetchall()]
            
            # Cargar bots del grupo
            cursor.execute('SELECT bot_index FROM bots WHERE group_name=?', (row['name'],))
            group.bots = [r['bot_index'] for r in cursor.fetchall()]
            
            self.groups[row['name']] = group
        
        # Cargar pool de proxies
        cursor.execute('SELECT proxy FROM proxy_pool')
        self.proxy_pool = [r['proxy'] for r in cursor.fetchall()]
        state.proxies = self.proxy_pool
        
        conn.close()
    
    def _save_bot(self, bot: BotInstance):
        """Guarda un bot en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        assignment = self.assignments.get(bot.index)
        group_name = self._get_bot_group(bot.index)
        
        cursor.execute('''
            INSERT OR REPLACE INTO bots
            (bot_index, account_data, status, proxy_address, group_name, assigned_to, service_id, expires_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            bot.index,
            json.dumps(bot.account_data),
            bot.status,
            bot.proxy_address or 'DIRECT',
            group_name,
            assignment.user_id if assignment else None,
            assignment.service_id if assignment else None,
            assignment.expires_at.isoformat() if assignment and assignment.expires_at else None
        ))
        
        conn.commit()
        conn.close()
    
    def _save_group(self, group: BotGroup):
        """Guarda un grupo en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO groups (name, user_id, config, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (group.name, group.user_id, json.dumps(group.config)))
        
        # Guardar proxies del grupo
        cursor.execute('DELETE FROM group_proxies WHERE group_name=?', (group.name,))
        for proxy in group.proxies:
            cursor.execute('INSERT INTO group_proxies (group_name, proxy) VALUES (?, ?)',
                         (group.name, proxy))
        
        conn.commit()
        conn.close()
    
    def _save_proxy_pool(self):
        """Guarda el pool de proxies"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM proxy_pool')
        for proxy in self.proxy_pool:
            cursor.execute('INSERT INTO proxy_pool (proxy) VALUES (?)', (proxy,))
        conn.commit()
        conn.close()
    
    def _get_bot_group(self, bot_index: int) -> Optional[str]:
        """Obtiene el grupo de un bot"""
        for group_name, group in self.groups.items():
            if bot_index in group.bots:
                return group_name
        return None
    
    # =========================================================================
    # GESTIÓN DE BOTS
    # =========================================================================
    
    def add_bot(self, account_data: list, group_name: str = None) -> int:
        """Agrega un nuevo bot al sistema."""
        with self.lock:
            idx = max(self.bots.keys()) + 1 if self.bots else 1
            
            bot = BotInstance(account_data, idx)
            if group_name and group_name in self.groups:
                self.groups[group_name].bots.append(idx)
            self.bots[idx] = bot
            
            self._save_bot(bot)
            self.logger.info(f"Bot #{idx} añadido" + (f" al grupo '{group_name}'" if group_name else ""))
            return idx
    
    def remove_bot(self, bot_index: int) -> bool:
        """Elimina un bot del sistema"""
        with self.lock:
            if bot_index not in self.bots:
                return False
            
            bot = self.bots[bot_index]
            if bot.client and bot.client.connected:
                threading.Thread(target=bot.client.disconnect, daemon=True).start()
            
            for group in self.groups.values():
                if bot_index in group.bots:
                    group.bots.remove(bot_index)
            
            if bot_index in self.assignments:
                del self.assignments[bot_index]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bots WHERE bot_index=?', (bot_index,))
            conn.commit()
            conn.close()
            
            del self.bots[bot_index]
            self.logger.info(f"Bot #{bot_index} eliminado")
            return True
    
    def assign_bot(self, bot_index: int, user_id: int, 
                   service_id: str = None, duration_hours: int = None) -> bool:
        """Asigna un bot a un usuario."""
        with self.lock:
            if bot_index not in self.bots:
                return False
            
            expires_at = None
            if duration_hours:
                expires_at = datetime.now() + timedelta(hours=duration_hours)
            
            assignment = BotAssignment(bot_index, user_id, service_id, expires_at)
            self.assignments[bot_index] = assignment
            
            self._save_bot(self.bots[bot_index])
            self.logger.info(f"Bot #{bot_index} asignado a usuario {user_id}" +
                           (f" por {duration_hours}h" if duration_hours else ""))
            return True
    
    def release_bot(self, bot_index: int) -> bool:
        """Libera un bot de su asignación"""
        with self.lock:
            if bot_index not in self.assignments:
                return False
            
            bot = self.bots.get(bot_index)
            if bot and bot.client and bot.client.connected:
                threading.Thread(target=bot.client.disconnect, daemon=True).start()
                bot.status = "idle"
            
            del self.assignments[bot_index]
            self._save_bot(self.bots[bot_index])
            self.logger.info(f"Bot #{bot_index} liberado")
            return True
    
    def start_bot(self, bot_index: int) -> bool:
        """Inicia un bot (conexión al juego)"""
        with self.lock:
            if bot_index not in self.bots:
                return False
            
            bot = self.bots[bot_index]
            
            if bot.client and bot.client.connected:
                return True
            
            proxy = self._get_proxy_for_bot(bot_index)
            bot.proxy_address = proxy
            
            threading.Thread(target=self._connect_bot_thread, args=(bot_index,), daemon=True).start()
            return True
    
    def stop_bot(self, bot_index: int) -> bool:
        """Detiene un bot"""
        with self.lock:
            if bot_index not in self.bots:
                return False
            
            bot = self.bots[bot_index]
            if bot.client and bot.client.connected:
                threading.Thread(target=bot.client.disconnect, daemon=True).start()
                bot.status = "offline"
                self._save_bot(bot)
                return True
            return False
    
    def _connect_bot_thread(self, bot_index: int):
        """Hilo de conexión para un bot"""
        bot = self.bots[bot_index]
        
        try:
            bot.set_status("preparing")
            
            hotel_config = self._get_hotel_for_bot(bot)
            
            proxy = bot.proxy_address
            sso_proxy = None
            if proxy != 'DIRECT':
                parts = proxy.split(':')
                sso_proxy = (f'socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                           if len(parts) == 4 else f'socks5://{parts[0]}:{parts[1]}')
            
            ticket = get_sso_ticket(bot.account_data, sso_proxy, base_url=hotel_config['base_url'])
            
            if not ticket:
                bot.set_status("expired")
                self.logger.error(f"Bot #{bot_index}: SSO ticket falló")
                self._save_bot(bot)
                return
            
            bot.sso_ticket = ticket
            bot.set_status("connecting")
            
            client = HabboClientGUI(
                sso_ticket=ticket,
                bot_index=bot.index,
                proxy=proxy,
                logger=bot.add_log,
                status_updater=bot.set_status,
                mute_updater=bot.set_mute_status,
                admin_auto_leave_enabled=True,
                hotel_config=hotel_config
            )
            
            bot.client = client
            
            if client.connect():
                bot.set_status("online")
                self.logger.info(f"Bot #{bot_index} conectado correctamente")
            else:
                bot.set_status("error")
                self.logger.error(f"Bot #{bot_index}: error de conexión")
            
            self._save_bot(bot)
            
        except Exception as e:
            bot.set_status("error")
            self.logger.error(f"Bot #{bot_index}: error - {e}")
            self._save_bot(bot)
    
    def _get_hotel_for_bot(self, bot: BotInstance) -> dict:
        """Obtiene la configuración del hotel para un bot"""
        hotel_key = state.hotel
        if isinstance(bot.account_data, list) and bot.account_data:
            if isinstance(bot.account_data[0], dict):
                hotel_key = bot.account_data[0].get('hotel', state.hotel)
        return const.HOTELS.get(hotel_key, const.HOTELS['habbo.com'])
    
    def _find_bot_by_service_id(self, service_id: str) -> Optional[int]:
        """Localiza el índice de bot por su service_id (UUID del backend web)"""
        for bot_index, assignment in self.assignments.items():
            if assignment.service_id == service_id:
                return bot_index
        return None

    def _get_proxy_for_bot(self, bot_index: int) -> str:
        """Obtiene un proxy para un bot (prioridad: grupo -> global)"""
        for group in self.groups.values():
            if bot_index in group.bots and group.proxies:
                proxy = group.proxies[group._proxy_idx % len(group.proxies)]
                group._proxy_idx += 1
                return proxy
        
        if self.proxy_pool:
            proxy = self.proxy_pool[self._proxy_idx % len(self.proxy_pool)]
            self._proxy_idx += 1
            return proxy
        
        return 'DIRECT'
    
    # =========================================================================
    # GESTIÓN DE GRUPOS
    # =========================================================================
    
    def create_group(self, name: str, user_id: int = None, config: dict = None) -> bool:
        """Crea un nuevo grupo de bots"""
        with self.lock:
            if name in self.groups:
                return False
            
            group = BotGroup(name, user_id, config)
            self.groups[name] = group
            self._save_group(group)
            
            self.logger.info(f"Grupo '{name}' creado")
            return True
    
    def delete_group(self, name: str) -> bool:
        """Elimina un grupo"""
        with self.lock:
            if name not in self.groups:
                return False
            
            for bot_index in self.groups[name].bots:
                if bot_index in self.bots:
                    self._save_bot(self.bots[bot_index])
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM groups WHERE name=?', (name,))
            cursor.execute('DELETE FROM group_proxies WHERE group_name=?', (name,))
            conn.commit()
            conn.close()
            
            del self.groups[name]
            self.logger.info(f"Grupo '{name}' eliminado")
            return True
    
    def add_bot_to_group(self, bot_index: int, group_name: str) -> bool:
        """Añade un bot a un grupo"""
        with self.lock:
            if bot_index not in self.bots or group_name not in self.groups:
                return False
            
            for group in self.groups.values():
                if bot_index in group.bots:
                    group.bots.remove(bot_index)
            
            self.groups[group_name].bots.append(bot_index)
            self._save_bot(self.bots[bot_index])
            self._save_group(self.groups[group_name])
            return True
    
    def add_proxy_to_group(self, group_name: str, proxy: str) -> bool:
        """Añade un proxy a un grupo"""
        with self.lock:
            if group_name not in self.groups:
                return False
            
            if proxy not in self.groups[group_name].proxies:
                self.groups[group_name].proxies.append(proxy)
                self._save_group(self.groups[group_name])
                return True
            return False
    
    def add_proxy_to_pool(self, proxy: str) -> bool:
        """Añade un proxy al pool global"""
        with self.lock:
            if proxy not in self.proxy_pool:
                self.proxy_pool.append(proxy)
                self._save_proxy_pool()
                state.proxies = self.proxy_pool
                return True
            return False
    
    def remove_proxy_from_pool(self, proxy: str) -> bool:
        """Elimina un proxy del pool global"""
        with self.lock:
            if proxy in self.proxy_pool:
                self.proxy_pool.remove(proxy)
                self._save_proxy_pool()
                state.proxies = self.proxy_pool
                return True
            return False
    
    # =========================================================================
    # ACCIONES DE BOTS
    # =========================================================================
    
    def execute_action(self, bot_index: int, action: str, **kwargs) -> dict:
        """Ejecuta una acción en un bot."""
        with self.lock:
            if bot_index not in self.bots:
                return {'success': False, 'error': 'Bot no encontrado'}
            
            bot = self.bots[bot_index]
            if not bot.client or not bot.client.connected:
                return {'success': False, 'error': 'Bot no conectado'}
            
            client = bot.client
            
            try:
                if action == 'shout':
                    msg = kwargs.get('msg', '')
                    style = kwargs.get('style', -1)
                    client.shout(msg, style)
                    
                elif action == 'whisper':
                    user = kwargs.get('user', '')
                    msg = kwargs.get('msg', '')
                    style = kwargs.get('style', 0)
                    client.whisper(user, msg, style)
                    
                elif action == 'walk':
                    x = kwargs.get('x', 0)
                    y = kwargs.get('y', 0)
                    client.walk(x, y)
                    
                elif action == 'dance':
                    style = kwargs.get('style', 0)
                    client.dance(style)
                    
                elif action == 'sign':
                    sign_id = kwargs.get('sign_id', 0)
                    client.sign(sign_id)
                    
                elif action == 'effect':
                    effect_id = kwargs.get('effect_id', 0)
                    client.enable_effect(effect_id)
                    
                elif action == 'join_room':
                    room_id = kwargs.get('room_id', 0)
                    client.join_room(room_id)
                    
                elif action == 'quit_room':
                    client.quit_room()
                    
                elif action == 'change_motto':
                    motto = kwargs.get('motto', '')
                    client.change_motto(motto)
                    
                elif action == 'update_figure':
                    gender = kwargs.get('gender', 'M')
                    figure = kwargs.get('figure', '')
                    client.update_figure(gender, figure)
                    
                elif action == 'respect_user':
                    user_id = kwargs.get('user_id', 0)
                    client.respect_user(user_id)
                    
                elif action == 'request_friend':
                    username = kwargs.get('username', '')
                    client.request_friend(username)
                    
                elif action == 'random_walk':
                    delay = kwargs.get('delay', 2.5)
                    client.set_walk_room_aware(True)
                    client.walk_random(delay)
                    
                elif action == 'stop_walk':
                    client.stop_random_walk()
                    
                elif action == 'get_users':
                    return {'success': True, 'users': list(client.users_in_room.values())}
                    
                else:
                    return {'success': False, 'error': f'Acción desconocida: {action}'}
                
                return {'success': True, 'action': action}
                
            except Exception as e:
                self.logger.error(f"Error en acción {action} para bot #{bot_index}: {e}")
                return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # MONITOREO Y MANTENIMIENTO
    # =========================================================================
    
    def start_monitor(self):
        """Inicia el hilo de monitoreo"""
        self.running = True
        self._stop_event.clear()
        
        def monitor_loop():
            while not self._stop_event.is_set():
                try:
                    self._check_bot_health()
                    self._clean_expired_assignments()
                    self._auto_reconnect()
                except Exception as e:
                    self.logger.error(f"Error en monitor: {e}")
                
                time.sleep(30)
        
        threading.Thread(target=monitor_loop, daemon=True).start()
        self.logger.info("Monitor iniciado")
    
    def stop_monitor(self):
        """Detiene el monitor"""
        self.running = False
        self._stop_event.set()
    
    def _check_bot_health(self):
        """Verifica la salud de los bots conectados"""
        for bot_index, bot in self.bots.items():
            if bot.client and bot.client.connected:
                if not bot.client.connected:
                    bot.status = "offline"
                    self._save_bot(bot)
    
    def _clean_expired_assignments(self):
        """Limpia asignaciones expiradas"""
        now = datetime.now()
        for bot_index, assignment in list(self.assignments.items()):
            if assignment.expires_at and assignment.expires_at < now:
                self.release_bot(bot_index)
                self.logger.info(f"Bot #{bot_index}: asignación expirada, liberado")
    
    def _auto_reconnect(self):
        """Auto-reconexión de bots caídos"""
        for bot_index, bot in self.bots.items():
            if bot.status in ("offline", "error") and bot.index in self.assignments:
                self.logger.info(f"Bot #{bot_index}: auto-reconectando...")
                self.start_bot(bot_index)
                time.sleep(2)
    
    # =========================================================================
    # API REST (Flask)
    # =========================================================================
    
    def _setup_routes(self):
        """Configura las rutas de la API REST"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({
                'status': 'ok',
                'bots': len(self.bots),
                'groups': len(self.groups),
                'online': sum(1 for b in self.bots.values() if b.status == 'online'),
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/api/bots', methods=['GET'])
        def get_bots():
            result = []
            for idx, bot in self.bots.items():
                result.append({
                    'index': idx,
                    'status': bot.status,
                    'name': bot.get_display_name().split(' [')[0],
                    'proxy': bot.proxy_address or 'DIRECT',
                    'group': self._get_bot_group(idx),
                    'assigned': idx in self.assignments,
                    'assigned_to': self.assignments[idx].user_id if idx in self.assignments else None,
                    'service_id': self.assignments[idx].service_id if idx in self.assignments else None,
                    'expires_at': self.assignments[idx].expires_at.isoformat() if idx in self.assignments and self.assignments[idx].expires_at else None
                })
            return jsonify(result)
        
        @self.app.route('/api/bots', methods=['POST'])
        def create_bot():
            data = request.get_json()
            if not data or 'account_data' not in data:
                return jsonify({'error': 'Falta account_data'}), 400
            
            account_data = data['account_data']
            group_name = data.get('group')
            
            idx = self.add_bot(account_data, group_name)
            return jsonify({'index': idx, 'message': f'Bot #{idx} creado'})
        
        @self.app.route('/api/bots/<int:bot_index>', methods=['DELETE'])
        def delete_bot(bot_index):
            if self.remove_bot(bot_index):
                return jsonify({'message': f'Bot #{bot_index} eliminado'})
            return jsonify({'error': 'Bot no encontrado'}), 404
        
        @self.app.route('/api/bots/<int:bot_index>/start', methods=['POST'])
        def start_bot(bot_index):
            if self.start_bot(bot_index):
                return jsonify({'message': f'Bot #{bot_index} iniciando...'})
            return jsonify({'error': 'Bot no encontrado'}), 404
        
        @self.app.route('/api/bots/<int:bot_index>/stop', methods=['POST'])
        def stop_bot(bot_index):
            if self.stop_bot(bot_index):
                return jsonify({'message': f'Bot #{bot_index} detenido'})
            return jsonify({'error': 'Bot no encontrado'}), 404
        
        @self.app.route('/api/bots/<int:bot_index>/assign', methods=['POST'])
        def assign_bot(bot_index):
            data = request.get_json()
            user_id = data.get('user_id')
            service_id = data.get('service_id')
            duration_hours = data.get('duration_hours')
            
            if not user_id:
                return jsonify({'error': 'Falta user_id'}), 400
            
            if self.assign_bot(bot_index, user_id, service_id, duration_hours):
                return jsonify({'message': f'Bot #{bot_index} asignado'})
            return jsonify({'error': 'Bot no encontrado'}), 404
        
        @self.app.route('/api/bots/<int:bot_index>/release', methods=['POST'])
        def release_bot(bot_index):
            if self.release_bot(bot_index):
                return jsonify({'message': f'Bot #{bot_index} liberado'})
            return jsonify({'error': 'Bot no asignado'}), 400
        
        @self.app.route('/api/bots/<int:bot_index>/action', methods=['POST'])
        def execute_bot_action(bot_index):
            data = request.get_json()
            action = data.get('action')
            if not action:
                return jsonify({'error': 'Falta action'}), 400
            
            kwargs = data.get('params', {})
            result = self.execute_action(bot_index, action, **kwargs)
            
            if result['success']:
                return jsonify(result)
            return jsonify({'error': result.get('error', 'Error desconocido')}), 400
        
        @self.app.route('/api/bots/<int:bot_index>/log', methods=['GET'])
        def get_bot_log(bot_index):
            if bot_index not in self.bots:
                return jsonify({'error': 'Bot no encontrado'}), 404
            
            return jsonify({
                'index': bot_index,
                'log': list(self.bots[bot_index].log_buffer)
            })
        
        @self.app.route('/api/groups', methods=['GET'])
        def get_groups():
            result = []
            for name, group in self.groups.items():
                result.append({
                    'name': name,
                    'user_id': group.user_id,
                    'bot_count': len(group.bots),
                    'proxy_count': len(group.proxies),
                    'bots': group.bots,
                    'proxies': group.proxies,
                    'config': group.config
                })
            return jsonify(result)
        
        @self.app.route('/api/groups', methods=['POST'])
        def create_group():
            data = request.get_json()
            name = data.get('name')
            user_id = data.get('user_id')
            config = data.get('config', {})
            
            if not name:
                return jsonify({'error': 'Falta name'}), 400
            
            if self.create_group(name, user_id, config):
                return jsonify({'message': f'Grupo "{name}" creado'})
            return jsonify({'error': 'El grupo ya existe'}), 400
        
        @self.app.route('/api/groups/<name>', methods=['DELETE'])
        def delete_group(name):
            if self.delete_group(name):
                return jsonify({'message': f'Grupo "{name}" eliminado'})
            return jsonify({'error': 'Grupo no encontrado'}), 404
        
        @self.app.route('/api/groups/<name>/bots', methods=['POST'])
        def add_bot_to_group_route(name):
            data = request.get_json()
            bot_index = data.get('bot_index')
            
            if bot_index is None:
                return jsonify({'error': 'Falta bot_index'}), 400
            
            if self.add_bot_to_group(bot_index, name):
                return jsonify({'message': f'Bot #{bot_index} añadido al grupo "{name}"'})
            return jsonify({'error': 'Bot o grupo no encontrado'}), 404
        
        @self.app.route('/api/groups/<name>/proxies', methods=['POST'])
        def add_proxy_to_group_route(name):
            data = request.get_json()
            proxy = data.get('proxy')
            
            if not proxy:
                return jsonify({'error': 'Falta proxy'}), 400
            
            if self.add_proxy_to_group(name, proxy):
                return jsonify({'message': f'Proxy "{proxy}" añadido al grupo "{name}"'})
            return jsonify({'error': 'Proxy ya existe o grupo no encontrado'}), 400
        
        @self.app.route('/api/proxies', methods=['GET'])
        def get_proxies():
            return jsonify({
                'proxies': self.proxy_pool,
                'count': len(self.proxy_pool)
            })
        
        @self.app.route('/api/proxies', methods=['POST'])
        def add_proxy():
            data = request.get_json()
            proxy = data.get('proxy')
            
            if not proxy:
                return jsonify({'error': 'Falta proxy'}), 400
            
            if self.add_proxy_to_pool(proxy):
                return jsonify({'message': f'Proxy "{proxy}" añadido al pool'})
            return jsonify({'error': 'Proxy ya existe'}), 400
        
        @self.app.route('/api/proxies', methods=['DELETE'])
        def delete_proxy():
            data = request.get_json()
            proxy = data.get('proxy')
            
            if not proxy:
                return jsonify({'error': 'Falta proxy'}), 400
            
            if self.remove_proxy_from_pool(proxy):
                return jsonify({'message': f'Proxy "{proxy}" eliminado'})
            return jsonify({'error': 'Proxy no encontrado'}), 404
        
        # ── /command  (llamado por el backend Node.js vía vps.js) ───────────
        @self.app.route('/command', methods=['POST'])
        def handle_command():
            # Autenticación por API key
            api_key = request.headers.get('X-Api-Key', '')
            expected = os.environ.get('BOT_VPS_API_KEY', '')
            if expected and api_key != expected:
                return jsonify({'error': 'Unauthorized'}), 401

            data    = request.get_json() or {}
            command = data.get('command')
            bot_id  = data.get('botId')          # UUID del bot en el backend web
            hotel   = data.get('hotel', 'habbo.com')
            room    = data.get('room')
            duration_hours = data.get('durationHours')
            user_id = data.get('userId', 0)

            # ── spawn: asigna un bot libre y lo conecta ──────────────────
            if command == 'spawn':
                free = [
                    idx for idx, b in self.bots.items()
                    if idx not in self.assignments and b.status in ('idle', 'offline', 'Idle')
                ]
                if not free:
                    return jsonify({'error': 'No hay bots disponibles en el pool'}), 503

                bot_index = free[0]
                self.assign_bot(bot_index, user_id, service_id=bot_id,
                                duration_hours=int(duration_hours) if duration_hours else None)
                self.start_bot(bot_index)

                # Unirse a la sala tras conexión (en hilo separado para no bloquear)
                if room:
                    def _join_later():
                        time.sleep(5)
                        self.execute_action(bot_index, 'join_room', room_id=str(room))
                    threading.Thread(target=_join_later, daemon=True).start()

                return jsonify({'ok': True, 'botIndex': bot_index,
                                'message': f'Bot #{bot_index} asignado y conectando'})

            # ── start: reconecta un bot ya asignado ──────────────────────
            elif command == 'start':
                idx = self._find_bot_by_service_id(bot_id)
                if idx is None:
                    return jsonify({'error': 'Bot no encontrado por service_id'}), 404
                self.start_bot(idx)
                return jsonify({'ok': True, 'botIndex': idx})

            # ── stop: desconecta sin liberar la asignación ───────────────
            elif command == 'stop':
                idx = self._find_bot_by_service_id(bot_id)
                if idx is None:
                    return jsonify({'error': 'Bot no encontrado por service_id'}), 404
                self.stop_bot(idx)
                return jsonify({'ok': True, 'botIndex': idx})

            # ── destroy: libera la asignación y desconecta ───────────────
            elif command == 'destroy':
                idx = self._find_bot_by_service_id(bot_id)
                if idx is None:
                    return jsonify({'ok': True, 'message': 'No había asignación activa'})
                self.release_bot(idx)
                return jsonify({'ok': True, 'botIndex': idx})

            # ── status: devuelve estado actual del bot ───────────────────
            elif command == 'status':
                idx = self._find_bot_by_service_id(bot_id)
                if idx is None:
                    return jsonify({'status': 'not_found'})
                bot = self.bots[idx]
                return jsonify({'ok': True, 'botIndex': idx, 'status': bot.status})

            # ── action: ejecuta una acción en el bot del usuario ─────────
            elif command == 'action':
                idx = self._find_bot_by_service_id(bot_id)
                if idx is None:
                    return jsonify({'error': 'Bot no encontrado'}), 404
                action_name = data.get('action')
                params      = data.get('params', {})
                if not action_name:
                    return jsonify({'error': 'Falta action'}), 400
                result = self.execute_action(idx, action_name, **params)
                if result.get('success'):
                    return jsonify({'ok': True, **result})
                return jsonify({'error': result.get('error', 'Error desconocido')}), 400

            return jsonify({'error': f'Comando desconocido: {command}'}), 400

        # ── /service  (ejecuta servicios de la tienda: respetos, room fill, etc.) ──
        @self.app.route('/service', methods=['POST'])
        def execute_service():
            api_key  = request.headers.get('X-Api-Key', '')
            expected = os.environ.get('BOT_VPS_API_KEY', '')
            if expected and api_key != expected:
                return jsonify({'error': 'Unauthorized'}), 401

            data       = request.get_json() or {}
            svc_type   = data.get('type')          # room_fill | badge_respect | badge_pet | raid
            order_id   = data.get('orderId')
            hotel      = data.get('hotel', 'habbo.com')
            habbo_name = data.get('habboName', '')
            room_id    = data.get('roomId')
            bot_count  = int(data.get('botCount', 1))
            duration_s = int(data.get('durationSeconds', 0))
            duration_h = max(1, duration_s // 3600) if duration_s else None

            # Bots libres disponibles para el hotel
            free = [
                idx for idx, b in self.bots.items()
                if idx not in self.assignments and b.status in ('idle', 'offline', 'Idle')
            ]

            if not free:
                return jsonify({'error': 'No hay bots disponibles en el pool', 'ok': False}), 503

            assigned = []

            # ── room_fill / raid: asignar N bots a la sala ──────────────────
            if svc_type in ('room_fill', 'raid'):
                take = min(bot_count, len(free))
                for idx in free[:take]:
                    self.assign_bot(idx, 0, service_id=order_id, duration_hours=duration_h)
                    self.start_bot(idx)
                    assigned.append(idx)

                if room_id:
                    def _join_room_later(indices, rid):
                        time.sleep(6)  # esperar conexión
                        for i in indices:
                            self.execute_action(i, 'join_room', room_id=str(rid))
                            time.sleep(0.5)
                    threading.Thread(target=_join_room_later, args=(assigned, room_id), daemon=True).start()

            # ── badge_respect: bots respetan al personaje objetivo ───────────
            elif svc_type == 'badge_respect':
                take = min(bot_count, len(free))
                for idx in free[:take]:
                    self.assign_bot(idx, 0, service_id=order_id, duration_hours=1)
                    self.start_bot(idx)
                    assigned.append(idx)

                def _respect_later(indices, name):
                    time.sleep(8)
                    for i in indices:
                        bot = self.bots.get(i)
                        if bot and bot.client and bot.client.connected:
                            # Buscar el user_id del personaje en la sala
                            users = self.execute_action(i, 'get_users').get('users', [])
                            target = next((u for u in users if u.get('name', '').lower() == name.lower()), None)
                            if target:
                                self.execute_action(i, 'respect_user', user_id=target.get('id', 0))
                        time.sleep(0.3)
                    # Liberar bots tras completar
                    time.sleep(5)
                    for i in indices:
                        self.release_bot(i)
                threading.Thread(target=_respect_later, args=(assigned, habbo_name), daemon=True).start()

            # ── badge_pet: bots acarician mascotas ───────────────────────────
            elif svc_type == 'badge_pet':
                take = min(bot_count, len(free))
                for idx in free[:take]:
                    self.assign_bot(idx, 0, service_id=order_id, duration_hours=1)
                    self.start_bot(idx)
                    assigned.append(idx)

                def _pet_later(indices, rid):
                    time.sleep(8)
                    for i in indices:
                        bot = self.bots.get(i)
                        if bot and bot.client and bot.client.connected and rid:
                            self.execute_action(i, 'join_room', room_id=str(rid))
                            time.sleep(1)
                            # Enviar paquete de caricia si el cliente lo soporta
                            if hasattr(bot.client, 'pet_scratch'):
                                try: bot.client.pet_scratch()
                                except: pass
                        time.sleep(0.3)
                    time.sleep(5)
                    for i in indices:
                        self.release_bot(i)
                threading.Thread(target=_pet_later, args=(assigned, room_id), daemon=True).start()

            else:
                return jsonify({'error': f'Tipo de servicio desconocido: {svc_type}'}), 400

            self.logger.info(f"Servicio '{svc_type}' iniciado | order={order_id} | bots={assigned}")
            return jsonify({'ok': True, 'assignedBots': assigned, 'count': len(assigned)})

        # ── /service/stop  (libera los bots de un pedido cuando expira) ──────
        @self.app.route('/service/stop', methods=['POST'])
        def stop_service():
            api_key  = request.headers.get('X-Api-Key', '')
            expected = os.environ.get('BOT_VPS_API_KEY', '')
            if expected and api_key != expected:
                return jsonify({'error': 'Unauthorized'}), 401

            data     = request.get_json() or {}
            order_id = data.get('orderId')
            released = []

            for bot_index, assignment in list(self.assignments.items()):
                if assignment.service_id == order_id:
                    bot = self.bots.get(bot_index)
                    if bot and bot.client and bot.client.connected:
                        try: self.execute_action(bot_index, 'quit_room')
                        except: pass
                    self.release_bot(bot_index)
                    released.append(bot_index)

            self.logger.info(f"Servicio parado | order={order_id} | bots liberados={released}")
            return jsonify({'ok': True, 'releasedBots': released})

        @self.app.route('/api/stats', methods=['GET'])
        def get_stats():
            online = sum(1 for b in self.bots.values() if b.status == 'online')
            assigned = len(self.assignments)
            
            return jsonify({
                'total_bots': len(self.bots),
                'online_bots': online,
                'offline_bots': len(self.bots) - online,
                'assigned_bots': assigned,
                'free_bots': len(self.bots) - assigned,
                'groups': len(self.groups),
                'proxies': len(self.proxy_pool),
                'timestamp': datetime.now().isoformat()
            })
    
    # =========================================================================
    # INICIO
    # =========================================================================
    
    def run(self):
        """Inicia el servicio completo"""
        self.logger.info(f"Iniciando HeadlessBotManager en puerto {self.port}")
        
        self.start_monitor()
        
        self.app.run(host='0.0.0.0', port=self.port, debug=False, threaded=True)

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Headless Bot Manager para Habbo')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                       help=f'Puerto para la API (default: {DEFAULT_PORT})')
    parser.add_argument('--db', type=str, default=DEFAULT_DB,
                       help=f'Ruta de la base de datos (default: {DEFAULT_DB})')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Nivel de logging')
    
    args = parser.parse_args()
    
    global LOG_LEVEL
    LOG_LEVEL = getattr(logging, args.log_level)
    
    manager = HeadlessBotManager(db_path=args.db, port=args.port)
    
    try:
        manager.run()
    except KeyboardInterrupt:
        manager.logger.info("Cerrando HeadlessBotManager...")
        manager.stop_monitor()
        sys.exit(0)

if __name__ == '__main__':
    main()