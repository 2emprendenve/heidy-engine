@echo off
echo ---------------------------------------------------
echo 🚀 INICIANDO DESPLIEGUE A PYTHONANYWHERE (VÍA GITHUB)
echo ---------------------------------------------------

echo.
echo [1/3] Añadiendo archivos modificados...
git add .

echo.
echo [2/3] Creando punto de guardado (Commit)...
git commit -m "Update: Operación Unicornio Blanco y métricas"

echo.
echo [3/3] Subiendo código a la nube...
git push origin master

echo.
echo ====================================================================
echo ✅ ¡CÓDIGO ENVIADO AL REPOSITORIO EXITOSAMENTE!
echo.
echo ⚠️  FALTA EL ÚLTIMO PASO MANUAL EN PYTHONANYWHERE:
echo.
echo 1. Entra a tu cuenta de PythonAnywhere.
echo 2. Abre una consola "Bash".
echo 3. Escribe este comando exacto y presiona Enter:
echo    cd heidy-engine ^&^& git pull
echo 4. Ve a la pestaña "Web" y haz clic en el botón verde "Reload".
echo.
echo ¡Con eso el pixel empezará a funcionar correctamente en el servidor!
echo ====================================================================
pause
