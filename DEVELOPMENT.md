# OpenHotspot - Documentación para Desarrolladores

## Arquitectura del Sistema

OpenHotspot está compuesto por cuatro módulos principales que trabajan juntos para crear y gestionar un punto de acceso Wi-Fi:

### 1. **NetworkManager** (`core/network_manager.py`)
Gestiona la configuración y control de la red hospedada (Hosted Network) en Windows.

**Funciones principales:**
- `start_hosted_network()`: Inicia la red hospedada
- `stop_hosted_network()`: Detiene la red hospedada
- `validate_credentials()`: Valida SSID y contraseña
- `generate_wifi_qr()`: Genera código QR con estándar WiFi
- `display_wifi_qr()`: Muestra QR en consola
- `get_hosted_network_status()`: Obtiene estado actual
- `validate_system_requirements()`: Verifica requisitos del sistema

**Requisitos:**
- Privilegios de Administrador
- Comando `netsh` disponible
- Controlador Wi-Fi compatible con Hosted Network

### 2. **ICSBridge** (`core/ics_bridge.py`)
Gestiona la Compartición de Conexión a Internet (ICS) entre adaptadores.

**Funciones principales:**
- `enable_ics()`: Activa compartición de internet
- `disable_ics()`: Desactiva compartición
- `list_connections()`: Lista adaptadores disponibles
- `detect_internet_interface()`: Detecta automáticamente interfaz con internet
- `find_virtual_adapter()`: Busca adaptador virtual del hotspot
- `get_ics_status()`: Obtiene estado de compartición

**Detalles técnicos:**
- Usa COM (Component Object Model) para acceder a HNetCfg
- Requiere privilegios de Administrador
- Mapea conexiones públicas (internet) a privadas (hotspot)

### 3. **ClientMonitor** (`core/client_monitor.py`)
Monitorea clientes conectados al hotspot en tiempo real.

**Funciones principales:**
- `scan_clients()`: Escanea clientes activos usando ARP
- `start_monitoring()`: Inicia monitoreo en background
- `stop_monitoring()`: Detiene monitoreo
- `get_clients()`: Obtiene lista de clientes
- `get_bandwidth_stats()`: Estadísticas de uso de ancho de banda
- `get_client_by_mac()`: Información detallada de un cliente
- `disconnect_client()`: Marca cliente como desconectado

**Estructura de datos:**
```python
@dataclass
class ClientInfo:
    mac_address: str           # Dirección MAC del cliente
    ip_address: str            # Dirección IP asignada
    hostname: Optional[str]    # Nombre de host resuelto
    signal_strength: Optional[int]  # Intensidad de señal
    connection_time: str       # Cuándo se conectó
    rx_bytes: int              # Bytes recibidos
    tx_bytes: int              # Bytes transmitidos
    last_activity: str         # Última actividad
```

### 4. **HotspotController** (`core/hotspot_controller.py`)
Orquesta los tres módulos anteriores como un sistema unificado.

**Funciones principales:**
- `start()`: Inicia hotspot completo (red + ICS + monitoreo)
- `stop()`: Detiene hotspot completamente
- `refresh()`: Reinicia sin perder configuración
- `get_status()`: Estado agregado del sistema
- `get_statistics()`: Estadísticas completas
- `get_detailed_report()`: Reporte detallado
- `update_credentials()`: Cambia SSID/contraseña
- `test_connection()`: Prueba conectividad a internet

**Flujo de ejecución:**
```
start() → [Validar credenciales] → [Iniciar red hospedada]
        → [Esperar 2s] → [Configurar ICS] → [Iniciar monitoreo]
        → [Retornar estado]
```

## Módulo de Utilidades (`core/utils.py`)

### ConsoleFormatter
Formatea mensajes para consola de manera compatible con Windows.

```python
ConsoleFormatter.success("Éxito")      # [OK] Éxito
ConsoleFormatter.error("Error")        # [ERROR] Error
ConsoleFormatter.warning("Aviso")      # [WARNING] Aviso
ConsoleFormatter.info("Información")   # [INFO] Información
ConsoleFormatter.header("Título")      # === Título ===
```

### ConfigValidator
Valida credenciales y datos del sistema.

```python
valid, msg = ConfigValidator.validate_ssid("MyNetwork")
valid, msg = ConfigValidator.validate_password("pass123")
valid, msg = ConfigValidator.validate_mac_address("AA:BB:CC:DD:EE:FF")
```

### FileHandler
Maneja operaciones de archivo (JSON, directorios).

### SystemInfo
Obtiene información del sistema (Python version, platform, IP config).

### Logger
Registra eventos en archivo de log.

## Interfaz CLI (`main.py`)

### Clases principales:

**DemoMode**
- Ejecuta validaciones sin necesidad de admin
- Prueba configuración de credenciales
- Valida requisitos del sistema
- Genera QR (sin compartir internet)

```bash
python main.py --demo
```

**CLIInterface**
- Interfaz interactiva de comandos
- Gestiona inicio/parada del hotspot
- Modo interactivo con comandos disponibles
- Genera reportes en consola

**Comandos disponibles:**
```
status       → Ver estado del hotspot
clientes     → Listar clientes conectados
reporte      → Mostrar reporte detallado
qr           → Mostrar código QR
refrescar    → Reiniciar hotspot
salir        → Detener y salir
ayuda        → Mostrar ayuda
```

## Flujo de Ejecución

### Modo Demo (sin admin)
```
main.py --demo
  ↓
DemoMode.validate_config()
  ├─ Validar SSID/Password
  ├─ Listar conexiones de red
  ├─ Generar código QR (sin guardarlo)
  ├─ Verificar requisitos del sistema
  └─ Mostrar estado
```

### Modo Real (con admin)
```
main.py --start --ssid "MyNet" --password "pass123"
  ↓
CLIInterface.start_hotspot()
  ├─ Validar credenciales
  ├─ Crear HotspotController
  ├─ Llamar controller.start()
  │   ├─ NetworkManager.start_hosted_network()
  │   ├─ ICSBridge.enable_ics()
  │   └─ ClientMonitor.start_monitoring()
  ├─ Mostrar QR
  └─ Entrar en modo interactivo
```

## Testing

Los tests se encuentran en `tests/test_core.py` y cubren:

- Validación de credenciales
- Operaciones de red
- Monitoreo de clientes
- Validación de configuración
- Formateo de consola
- Integración de módulos

**Ejecutar tests:**
```bash
pytest tests/test_core.py -v
```

**Cobertura de código:**
```bash
pytest tests/test_core.py --cov=core --cov-report=html
```

## Manejo de Errores

El sistema maneja excepciones en varios niveles:

1. **NetworkManager**: Captura errores de `netsh`
2. **ICSBridge**: Captura excepciones de COM y permisos
3. **ClientMonitor**: Captura errores de `arp` y resolución de DNS
4. **HotspotController**: Agrupa errores de subsistemas
5. **CLI**: Captura errores fatales y cancellación del usuario

## Requisitos del Sistema

- **OS**: Windows 7 o superior (optimizado para Windows 10+)
- **Python**: 3.8 o superior
- **Privilegios**: Administrador (para modo real)
- **Hardware**: Adaptador Wi-Fi compatible con Hosted Network
- **Conexión**: Ethernet o Wi-Fi con acceso a internet

## Dependencias principales

```
qrcode>=7.4.2         # Generación de códigos QR
pillow>=10.1.0        # Procesamiento de imágenes
pywin32>=306          # Acceso a APIs de Windows
pytest>=8.0.0         # Testing
pytest-cov>=4.0.0     # Cobertura de tests
comtypes>=1.4.4       # Acceso a COM (ICS)
psutil>=6.0.0         # Estadísticas del sistema
requests>=2.31.0      # Pruebas de conectividad
colorama>=0.4.6       # Colores en consola
tabulate>=0.9.0       # Tablas formateadas
```

## Estructura de directorios

```
OpenHotspot/
├── main.py                     # Punto de entrada
├── core/
│   ├── __init__.py            # Exporta módulos
│   ├── network_manager.py      # Gestión de red
│   ├── ics_bridge.py           # Compartición de internet
│   ├── client_monitor.py       # Monitoreo de clientes
│   ├── hotspot_controller.py   # Orquestación
│   └── utils.py                # Utilidades
├── tests/
│   └── test_core.py            # Tests unitarios
├── assets/                     # Imágenes, recursos
├── requirements.txt            # Dependencias
├── README.md                   # Documentación principal
├── QUICK_REFERENCE.md          # Referencia rápida
└── build.spec                  # Configuración de PyInstaller
```

## Contribución

Para contribuir al proyecto:

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/mi-feature`)
3. Realiza cambios
4. Ejecuta tests (`pytest tests/test_core.py`)
5. Commit cambios (`git commit -am 'Agregar feature'`)
6. Push a la rama (`git push origin feature/mi-feature`)
7. Abre Pull Request

## Notas de Desarrollo

- **Unicode en Windows**: Se usa `ConsoleFormatter` para compatibilidad
- **Admin Check**: Siempre validar con `is_admin()` antes de operaciones del sistema
- **Threading**: `ClientMonitor` usa hilos para monitoreo no-bloqueante
- **COM**: Inicialización lazy para `ICSBridge.net_share`
- **Logging**: Usar `logging` estándar de Python

## Future Roadmap

- [ ] GUI con PyQt/Tkinter
- [ ] Persistencia de configuración
- [ ] Bloqueo/limitación de clientes
- [ ] Estadísticas histórico
- [ ] Notificaciones de eventos
- [ ] Soporte para otros idiomas
- [ ] Compilación a .exe (PyInstaller)
