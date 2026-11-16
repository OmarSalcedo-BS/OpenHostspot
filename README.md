# OpenHotspot 🚀

Aplicación para Windows que inicia un punto de acceso Wi-Fi Direct desde su
interfaz gráfica y puede configurar la compartición de internet mediante ICS.
La conexión de clientes y el acceso a internet dependen del hardware y deben
verificarse en cada equipo.

## ✨ Características

- **Crear una red Wi-Fi Direct** - Requiere un controlador compatible con Wi-Fi Direct GO
- **Compartir internet (ICS)** - Selecciona la conexión de origen; el destino se detecta automáticamente
- **Generación de códigos QR** - Para conexión rápida de dispositivos
- **Dispositivos observados** - Vecinos IPv4 del adaptador del hotspot, sin prometer un inventario completo
- **Velocidad** - Tráfico del adaptador en tiempo real y prueba de internet bajo demanda
- **Interfaz gráfica** - Sin consola al usar la entrada gráfica, solicita administrador e integra los ajustes
- **Código modular y extensible** - Arquitectura limpia para fácil mantenimiento

## 📋 Requisitos

- **Windows 10/11** con adaptador Wi-Fi compatible
- **Python 3.10+** (probado en 3.14.8)
- **Privilegios de Administrador** (para crear hotspot)
- **Conexión Ethernet o WiFi** como fuente de internet
- **Wi-Fi Direct GO compatible**. Verifica con `netsh wlan show wirelesscapabilities`.

## ⚡ Instalación

```bash
# Clonar o descargar el repositorio
git clone https://github.com/tu-usuario/OpenHotspot.git
cd OpenHotspot/OpenHotspot

# Crear entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1  # PowerShell
# o
.\venv\Scripts\activate.bat  # CMD

# Instalar dependencias
pip install -r requirements.txt
```

## 🚀 Uso Rápido

```powershell
# Interfaz gráfica sin consola (Windows solicitará permisos de administrador)
.\venv\Scripts\pythonw.exe gui.pyw

# Ver todas las opciones
python main.py --help
```

En la interfaz selecciona la conexión con internet (por ejemplo, Ethernet), el
nombre y la contraseña. OpenHotspot observa los adaptadores Wi-Fi Direct y
trata de identificar automáticamente el que se activa al iniciar. Si ya hay
un adaptador Wi-Fi Direct activo, no inicia una nueva sesión; cierra la aplicación
que lo usa antes de continuar. Si no puede identificar un único destino estable,
no modifica ICS. Si ya hay otra compartición ICS activa, la aplicación no la reemplaza.
Si ICS falla, la aplicación informa de que el anuncio se inició sin compartir
internet. Incluso cuando ICS se configura, comprueba la conexión desde un
dispositivo: no se garantiza que Wi-Fi Direct proporcione acceso a internet.

La interfaz usa Wi-Fi Direct, no el botón de zona móvil de Windows. Wi-Fi como
origen podría requerir compatibilidad de funcionamiento simultáneo; no se ha
verificado un modo repetidor. La vista Dispositivos consulta los vecinos IPv4
observados por Windows en el adaptador detectado: pueden estar desactualizados
o faltar dispositivos, por lo que no es un listado fiable de conexiones activas.
No se muestran velocidades por cliente. El tráfico enviado y recibido es el
total del adaptador, no necesariamente solo tráfico de internet.
La asociación automática se basa en los cambios observados en Windows y no es
una identificación directa del publicador; evita iniciar otras sesiones Wi-Fi
Direct simultáneamente. El encaminamiento usa ICS de Windows, no el motor
propietario de Connectify, por lo que su comportamiento puede ser diferente.

La prueba de velocidad es una estimación con una descarga de 10 MiB y una
subida de 3 MiB a Cloudflare. Consume datos, revela la IP pública a ese
servicio y usa la ruta predeterminada del equipo, que puede no ser la conexión
seleccionada para compartir. Se ejecuta únicamente al pulsar «Medir internet».
El bloqueo de internet por dispositivo y la lista blanca persistente todavía
no están disponibles: el motor actual no los aplica de forma verificable.

El inicio gráfico oculta la consola propia de la aplicación; una terminal
desde la que se lance permanece abierta, y Windows sigue mostrando el aviso
UAC. Los errores se registran en `%LOCALAPPDATA%\OpenHotspot\openhotspot.log`.

## 📖 Documentación Detallada

### Comandos CLI

La CLI todavía usa la API antigua `netsh wlan hostednetwork`, diferente de la
interfaz gráfica, y requiere soporte de red hospedada.

| Comando | Descripción |
|---------|-------------|
| `--start` | Inicia el hotspot |
| `--interfaces` | Intenta listar las conexiones mediante ICS |
| `--ssid NOMBRE` | Nombre de red (máx 32 caracteres) |
| `--password PASS` | Contraseña (8-63 caracteres) |
| `--public-if NOMBRE` | Interfaz de internet (default: Ethernet) |

Al iniciar desde la consola, usa el comando interactivo `salir` para detenerla.
Los comandos independientes `--status` y `--stop` no consultan una sesión previa.

### Módulos del Proyecto

#### `core/wifi_direct.py` y `core/direct_controller.py`
Inician y detienen Wi-Fi Direct desde la interfaz, y coordinan ICS.

#### `core/network_manager.py`
Valida credenciales, genera QR y gestiona la red hospedada antigua para la CLI.
- `start_hosted_network()` - Inicia el hotspot
- `stop_hosted_network()` - Detiene el hotspot
- `get_hosted_network_status()` - Obtiene estado actual
- `generate_wifi_qr()` - Genera código QR
- `validate_credentials()` - Valida SSID y contraseña

#### `core/ics_bridge.py`
Gestiona la compartición de conexión a internet usando COM
- `enable_ics()` - Activa compartición de internet
- `disable_ics()` - Desactiva compartición
- `list_connections()` - Lista conexiones de red
- `get_ics_status()` - Obtiene estado del ICS

#### `core/client_monitor.py`
Monitor antiguo experimental utilizado por la CLI; sus observaciones ARP no
confirman clientes conectados ni permiten medir tráfico o desconectarlos.
- `scan_clients()` - Escanea clientes activos
- `get_clients()` - Lista clientes conectados
- `start_monitoring()` - Inicia monitoreo automático
- `get_statistics()` - Obtiene estadísticas de uso

#### `core/hotspot_observer.py` y `core/speed_test.py`
Observan vecinos y contadores del adaptador, y realizan la prueba de velocidad.

#### `ui/`
Vistas y estilos compartidos de la interfaz gráfica.

## 🧪 Pruebas

```powershell
# Ejecutar suite de tests
python -m pytest tests -v

# Con cobertura
python -m pytest tests --cov=core
```


## 📦 Estructura del Proyecto

```
OpenHotspot/
├── main.py                    # Punto de entrada
├── gui.py                     # Interfaz gráfica CustomTkinter
├── requirements.txt           # Dependencias
├── README.md                  # Este archivo
├── QUICK_REFERENCE.md         # Referencia rápida
├── .gitignore                 # Archivos a ignorar
├── core/
│   ├── __init__.py
│   ├── network_manager.py     # Gestión de hotspot
│   ├── wifi_direct.py         # Wi-Fi Direct
│   ├── direct_controller.py  # Orquestación de Wi-Fi Direct e ICS
│   ├── ics_bridge.py          # Compartición de internet
│   └── client_monitor.py      # Monitoreo de clientes
├── tests/
│   ├── __init__.py
│   └── test_core.py           # Tests unitarios
└── venv/                       # Virtual environment (no incluir)
```

## 🐛 Solución de Problemas

### No se puede iniciar Wi-Fi Direct
Ejecuta `netsh wlan show wirelesscapabilities` y busca `Wi-Fi Direct GO`.
La zona móvil de Windows y Wi-Fi Direct pueden entrar en conflicto. La
compatibilidad indicada por el controlador no garantiza acceso a internet.

### Error: "Se requieren privilegios de Administrador"
Abre PowerShell/CMD como administrador:
```powershell
# Click derecho en PowerShell → "Ejecutar como administrador"
```

### Hotspot no comparte internet
```powershell
# Verifica interfaces de red
netsh interface show interface

# Revisa si ya hay un adaptador Wi-Fi Direct activo
Get-NetAdapter -IncludeHidden
```

### Los clientes no se conectan
- Verifica que el adaptador Wi-Fi soporte Wi-Fi Direct GO
- Reinicia el hotspot
- Prueba un SSID más simple

## 🚀 Próximas Mejoras

- [ ] Soporte para la zona móvil moderna de Windows
- [ ] Limitación de ancho de banda por cliente
- [ ] Bloqueo/desbloqueamiento de clientes
- [ ] Historial de conexiones
- [ ] API REST
- [ ] Instalador de Windows

## 📄 Licencia

Este proyecto se distribuye bajo la licencia **MIT**. Ver archivo [LICENSE](LICENSE) para más detalles.

```
MIT License

Copyright (c) 2026 OpenHotspot Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Para contribuir:

1. **Fork** el repositorio
2. **Crea una rama** para tu feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** tus cambios (`git commit -m 'Add AmazingFeature'`)
4. **Push** a la rama (`git push origin feature/AmazingFeature`)
5. **Abre un Pull Request**

### Directrices de Contribución

- Mantén el código limpio y bien documentado
- Incluye tests para nuevas funcionalidades
- Actualiza el README si es necesario
- Sigue las convenciones de código existentes

## 📝 Notas de Desarrollo

### Requisitos Técnicos
- Requiere acceso a APIs de Windows (netsh, COM)
- Solo funciona en Windows 10/11
- Necesita privilegios administrativos para operaciones de red

### Arquitectura
- **NetworkManager**: Interfaz con netsh para hostspot
- **ICSBridge**: Interfaz COM con HNetCfg para ICS
- **ClientMonitor**: Escaneo ARP y resolución DNS
- **HotspotController**: Orquestador de módulos

## 💡 Inspiración y Propósito Educativo

Este proyecto demuestra:
- Automatización de sistemas operativos
- Objetos COM (Component Object Model)
- Threading y concurrencia
- Generación de códigos QR
- Desarrollo modular en Python
- Testing unitario con pytest
- Diseño de CLI con argparse

## 👥 Autores

- **Desarrollador Principal**: [OmarSalcedo-BS]
- **Contributores**: Ver [CONTRIBUTORS.md](CONTRIBUTORS.md)

## 📞 Contacto y Soporte

- **Issues**: [GitHub Issues](https://github.com/tu-usuario/OpenHotspot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/tu-usuario/OpenHotspot/discussions)
- **Email**: salcedosolarteomar@gmail.com

## 🙏 Agradecimientos

Gracias a:
- La comunidad de Python
- PyQRCode y Pillow por generación de QR
- pywin32 por acceso a APIs de Windows
- pytest por testing robusto

---

**OpenHotspot** - Punto de acceso Wi-Fi avanzado para Windows 🚀

*Made with ❤️ by the OpenHotspot community*
