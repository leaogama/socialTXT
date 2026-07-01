@echo off
echo =========================================
echo Reiniciando o servidor SocialTXT MCP...
echo =========================================
echo.

docker compose down
docker compose up -d

echo.
echo =========================================
echo Servidor reiniciado com sucesso!
echo.
echo A interface grafica esta disponivel em:
echo http://localhost:8000
echo =========================================
echo.
pause
