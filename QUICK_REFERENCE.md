# OpenHotspot - Referencia rápida

Ejecuta estos comandos desde la carpeta del proyecto en PowerShell:

```powershell
# Instalar dependencias en el entorno virtual
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Abrir interfaz gráfica sin consola; solicita permisos de administrador
.\venv\Scripts\pythonw.exe gui.pyw

# Comprobar si el controlador admite Wi-Fi Direct GO
netsh wlan show wirelesscapabilities

# Ver nombres de adaptadores, incluidos los virtuales
Get-NetAdapter -IncludeHidden

# Ejecutar pruebas
.\venv\Scripts\python.exe -m pytest tests -q
```

Selecciona solo la conexión de internet: el adaptador virtual se detecta
automáticamente. Si hay otra sesión Wi-Fi Direct activa, ciérrala antes de
iniciar. ICS no se modifica si la detección es ambigua o ya hay otra
compartición. La aplicación no controla la zona móvil de Windows; verifica
el acceso a internet desde un dispositivo conectado. La CLI utiliza el
mecanismo antiguo de red hospedada.

En Dispositivos se muestran vecinos IPv4 observados y tráfico total del
adaptador, no una lista completa ni velocidades por cliente. La prueba de
velocidad usa Cloudflare y la ruta predeterminada del equipo. El bloqueo y
la lista blanca aún no están disponibles. El registro está en
`%LOCALAPPDATA%\OpenHotspot\openhotspot.log`.
