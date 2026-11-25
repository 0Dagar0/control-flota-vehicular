# Registra en el Programador de tareas de Windows los tres trabajos de la v1.0.
# Se ejecuta una sola vez por equipo. No guarda contraseñas: usa la sesión del usuario actual.
#
# Uso (desde cualquier carpeta):
#   powershell -ExecutionPolicy Bypass -File "P:\...\App\scripts\registrar_tareas_notificaciones.ps1"
#
# Las tareas se llaman MiFlota-* y se pueden revisar con:
#   Get-ScheduledTask -TaskName 'MiFlota-*' | Select TaskName,State

$ErrorActionPreference = "Stop"

$app = Split-Path -Parent $PSScriptRoot
$python = Join-Path $app ".venv\Scripts\python.exe"
$manage = Join-Path $app "manage.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "No se encontró el Python del entorno virtual: $python"
}
if (-not (Test-Path -LiteralPath $manage)) {
    throw "No se encontró manage.py en: $app"
}

$usuario = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$ajustes = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

function Register-MiFlotaTarea {
    param(
        [string]$Nombre,
        [string]$Argumentos,
        [object]$Disparador,
        [string]$Descripcion
    )
    # La ruta de manage.py tiene espacios: va entre comillas dentro de los argumentos.
    # Execute y WorkingDirectory se pasan sin comillas: el Programador las añade si hace falta.
    $accion = New-ScheduledTaskAction -Execute $python -Argument $Argumentos -WorkingDirectory $app
    Register-ScheduledTask `
        -TaskName $Nombre `
        -Action $accion `
        -Trigger $Disparador `
        -Principal $principal `
        -Settings $ajustes `
        -Description $Descripcion `
        -Force | Out-Null
    Write-Host "Registrada: $Nombre"
}

# 1) Cola de envíos: reintenta, escala críticos y envía lo pendiente cada minuto.
$cadaminuto = New-ScheduledTaskTrigger `
    -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
Register-MiFlotaTarea -Nombre "MiFlota-Cola-Notificaciones" `
    -Argumentos "`"$manage`" enviar_notificaciones" `
    -Disparador $cadaminuto `
    -Descripcion "Procesa la cola de notificaciones cada minuto (v1.0)."

# 2) Resumen diario de las 07:00.
$las7 = New-ScheduledTaskTrigger -Daily -At "07:00"
Register-MiFlotaTarea -Nombre "MiFlota-Resumen-Diario" `
    -Argumentos "`"$manage`" enviar_notificaciones --resumen" `
    -Disparador $las7 `
    -Descripcion "Genera y envía el resumen diario de documentos y mantenimientos."

# 3) Inspecciones pendientes al mediodía.
$mediodia = New-ScheduledTaskTrigger -Daily -At "12:00"
Register-MiFlotaTarea -Nombre "MiFlota-Inspecciones-Mediodia" `
    -Argumentos "`"$manage`" enviar_notificaciones --mediodia" `
    -Disparador $mediodia `
    -Descripcion "Avisa de las inspecciones que siguen en progreso al mediodía."

Write-Host ""
Get-ScheduledTask -TaskName "MiFlota-*" | Select-Object TaskName,State | Format-Table -AutoSize
Write-Host "Las tareas se ejecutan con la sesión de $usuario iniciada."
