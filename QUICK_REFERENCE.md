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

# Generar la próxima versión del ejecutable en dist\OpenHotspot-VERSION
.\venv\Scripts\python.exe build.py
```

Selecciona solo la conexión de internet: el adaptador virtual se detecta
automáticamente. Si hay otra sesión Wi-Fi Direct activa, ciérrala antes de
iniciar. ICS no se modifica si la detección es ambigua o ya hay otra
compartición. La aplicación no controla la zona móvil de Windows; verifica
el acceso a internet desde un dispositivo conectado. La CLI utiliza el
mecanismo antiguo de red hospedada.

El QR aparece al iniciar. La pantalla principal muestra conexiones informadas
por Wi-Fi Direct y tráfico total del adaptador; Dispositivos incluye además
los vecinos IPv4 observados. No se garantiza una lista completa ni se muestran
velocidades por cliente. La prueba de
velocidad usa Cloudflare y la ruta predeterminada del equipo. El bloqueo y
la lista blanca aún no están disponibles. El registro está en
`%LOCALAPPDATA%\OpenHotspot\openhotspot.log`.

En Ajustes puedes guardar la red, activar la apertura al iniciar sesión
(sin iniciar el hotspot), evitar la suspensión automática durante una sesión
y configurar QR, avisos y unidades. El inicio puede requerir confirmación UAC;
la prevención no impide suspensión manual ni que se apague la pantalla.
El archivo `%LOCALAPPDATA%\OpenHotspot\settings.json` guarda la contraseña
cifrada con DPAPI para el usuario de Windows que ejecuta la aplicación.

Para compartir el ejecutable, copia la carpeta de versión completa, incluida
`_internal`. `app_info.json` contiene la versión central; el script incrementa
el patch al compilar correctamente. El ejecutable solicita UAC y no está firmado.
