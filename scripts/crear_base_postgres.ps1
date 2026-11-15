# Crea la base y el usuario de PostgreSQL 18 para Mi Flota, y actualiza el .env.
#
# Uso (desde la carpeta App):
#   pwsh -File .\scripts\crear_base_postgres.ps1
#
# Qué hace:
#   1. Pide la contraseña del usuario `postgres` (no se guarda ni se muestra).
#   2. Genera una contraseña aleatoria para el usuario de la aplicación.
#   3. Crea el rol y la base `mi_flota` si no existen y ajusta la contraseña.
#   4. Escribe DB_ENGINE=postgresql y DB_PASSWORD en el .env sin imprimir la clave.
#   5. Comprueba la conexión con el usuario nuevo.
#
# Es seguro ejecutarlo varias veces: no borra datos.

$ErrorActionPreference = "Stop"

$app = Split-Path -Parent $PSScriptRoot
$archivoEnv = Join-Path $app ".env"
$psql = "P:\Program Files\PostgreSQL\18\bin\psql.exe"
$nombreBase = "mi_flota"
$usuarioApp = "mi_flota"

if (-not (Test-Path -LiteralPath $psql)) {
    throw "No se encontró psql en '$psql'. Ajusta la ruta al inicio de este script."
}
if (-not (Test-Path -LiteralPath $archivoEnv)) {
    throw "No se encontró .env en '$app'. Copia .env.example a .env antes de continuar."
}

Write-Host ""
Write-Host "=== Mi Flota · creación de la base de datos ===" -ForegroundColor Cyan
Write-Host "Se necesita la contraseña del usuario 'postgres' (la que definiste al instalar PostgreSQL)." -ForegroundColor Yellow
$seguro = Read-Host "Contraseña de postgres" -AsSecureString
$puntero = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
$clavePostgres = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($puntero)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($puntero)

if ([string]::IsNullOrWhiteSpace($clavePostgres)) {
    throw "No escribiste la contraseña de 'postgres'. Vuelve a ejecutar el script y escríbela (no se muestra en pantalla)."
}

# Contraseña aleatoria para la aplicación: 24 caracteres sin comillas ni símbolos raros.
$caracteres = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$buffer = New-Object byte[] 24
$rng.GetBytes($buffer)
$claveApp = -join ($buffer | ForEach-Object { $caracteres[$_ % $caracteres.Length] })

try {
    $env:PGPASSWORD = $clavePostgres

    Write-Host "Creando el rol '$usuarioApp'…" -ForegroundColor Gray
    $sqlRol = "DO `$`$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$usuarioApp') THEN CREATE ROLE $usuarioApp LOGIN; END IF; END `$`$; " +
              "ALTER ROLE $usuarioApp WITH LOGIN PASSWORD '$claveApp';"
    & $psql -w -U postgres -h localhost -d postgres -v ON_ERROR_STOP=1 -q -c $sqlRol
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el rol. Revisa la contraseña de postgres (código $LASTEXITCODE)." }

    # Se usa COUNT(*) para que la consulta siempre devuelva una linea ("1" o "0").
    # Si no existiera ninguna base, psql no imprimiria nada y PowerShell daria $null.
    $existe = (& $psql -w -U postgres -h localhost -d postgres -tAc "SELECT COUNT(*) FROM pg_database WHERE datname = '$nombreBase'")
    if ($LASTEXITCODE -ne 0) { throw "No se pudo comprobar si existe la base '$nombreBase' (código $LASTEXITCODE)." }
    $existe = "$existe".Trim()
    Write-Host "Bases llamadas '$nombreBase': $existe" -ForegroundColor Gray
    if ($existe -ne "1") {
        Write-Host "Creando la base '$nombreBase'…" -ForegroundColor Gray
        & $psql -w -U postgres -h localhost -d postgres -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE $nombreBase OWNER $usuarioApp"
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la base." }
    } else {
        Write-Host "La base '$nombreBase' ya existía: se conserva." -ForegroundColor Gray
    }

    & $psql -w -U postgres -h localhost -d postgres -v ON_ERROR_STOP=1 -q -c "ALTER DATABASE $nombreBase OWNER TO $usuarioApp"
    if ($LASTEXITCODE -ne 0) { throw "No se pudo asignar el dueño de la base a '$usuarioApp' (código $LASTEXITCODE)." }

    # Actualiza el .env sin imprimir la contraseña.
    $lineas = @(Get-Content -LiteralPath $archivoEnv -Encoding UTF8)
    $tieneBase = $false
    $tieneUsuario = $false
    $tieneClave = $false
    $lineas = $lineas | ForEach-Object {
        if ($_ -match '^\s*DB_ENGINE\s*=') { 'DB_ENGINE=postgresql' }
        elseif ($_ -match '^\s*DB_NAME\s*=') { $script:tieneBase = $true; "DB_NAME=$nombreBase" }
        elseif ($_ -match '^\s*DB_USER\s*=') { $script:tieneUsuario = $true; "DB_USER=$usuarioApp" }
        elseif ($_ -match '^\s*DB_PASSWORD\s*=') { $script:tieneClave = $true; "DB_PASSWORD=$claveApp" }
        else { $_ }
    }
    if (-not $tieneBase) { $lineas += "DB_NAME=$nombreBase" }
    if (-not $tieneUsuario) { $lineas += "DB_USER=$usuarioApp" }
    if (-not $tieneClave) { $lineas += "DB_PASSWORD=$claveApp" }
    if (-not ($lineas -match '^\s*DB_HOST\s*=')) { $lineas += "DB_HOST=localhost" }
    if (-not ($lineas -match '^\s*DB_PORT\s*=')) { $lineas += "DB_PORT=5432" }
    Set-Content -LiteralPath $archivoEnv -Value $lineas -Encoding UTF8

    # Comprueba que la aplicación puede entrar con su propio usuario.
    $env:PGPASSWORD = $claveApp
    $prueba = & $psql -w -U $usuarioApp -h localhost -d $nombreBase -tAc "SELECT current_database() || ' / ' || current_user"
    if ($LASTEXITCODE -ne 0) { throw "La base se creó pero la conexión con '$usuarioApp' falló (código $LASTEXITCODE)." }
    $prueba = "$prueba".Trim()

    Write-Host ""
    Write-Host "Listo. Conexión comprobada: $prueba" -ForegroundColor Green
    Write-Host "La contraseña de la aplicación quedó guardada solo en .env (no se muestra)." -ForegroundColor Green
    Write-Host ""
    Write-Host "Siguiente paso:" -ForegroundColor Cyan
    Write-Host "  .venv\Scripts\python.exe manage.py migrate" -ForegroundColor White
}
finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    $claveApp = $null
    $clavePostgres = $null
}
