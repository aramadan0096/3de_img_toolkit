Param()

$ErrorActionPreference = "Stop"

$toolkitRoot = (Resolve-Path (Join-Path $PSScriptRoot ".")).Path
$defaultPluginRoot = "C:\\Program Files\\3DE4\\sys_data\\py_scripts"

function Resolve-WritablePluginRoot([string]$initialRoot) {
    $candidate = $initialRoot

    while ($true) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            $candidate = $defaultPluginRoot
        }

        $candidate = [System.IO.Path]::GetFullPath($candidate)

        if (-not (Test-Path -LiteralPath $candidate)) {
            $create = Read-Host "Path does not exist. Create it? [y/N]"
            if ($create -match "^(y|yes)$") {
                try {
                    New-Item -ItemType Directory -Path $candidate -Force -ErrorAction Stop | Out-Null
                }
                catch {
                    Write-Host "Cannot create directory: $candidate" -ForegroundColor Red
                    Write-Host "Reason: $($_.Exception.Message)" -ForegroundColor Red
                    $candidate = Read-Host "Enter another plugin scripts directory (or Q to quit)"
                    if ($candidate -match "^(q|quit)$") {
                        throw "Installer aborted by user."
                    }
                    continue
                }
            }
            else {
                $candidate = Read-Host "Enter another plugin scripts directory (or Q to quit)"
                if ($candidate -match "^(q|quit)$") {
                    throw "Installer aborted by user."
                }
                continue
            }
        }

        try {
            $probeName = ".write_test_{0}.tmp" -f ([Guid]::NewGuid().ToString("N"))
            $probePath = Join-Path $candidate $probeName
            Set-Content -LiteralPath $probePath -Value "ok" -Encoding ASCII -ErrorAction Stop
            Remove-Item -LiteralPath $probePath -Force -ErrorAction Stop
            return $candidate
        }
        catch {
            Write-Host "No write permission for: $candidate" -ForegroundColor Red
            Write-Host "Reason: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "Tip: Run PowerShell as Administrator or choose a user-writable scripts path." -ForegroundColor Yellow
            $candidate = Read-Host "Enter another plugin scripts directory (or Q to quit)"
            if ($candidate -match "^(q|quit)$") {
                throw "Installer aborted by user."
            }
        }
    }
}

Write-Host "Image Toolkit proxy installer"
Write-Host "Toolkit root (static path to embed): $toolkitRoot"
Write-Host ""

$pluginRoot = Read-Host "Enter 3DEqualizer plugin scripts directory [$defaultPluginRoot]"
$pluginRoot = Resolve-WritablePluginRoot $pluginRoot

$targetDir = $pluginRoot

$escapedToolkitRoot = $toolkitRoot.Replace("\\", "/")

$proxyTemplatePath = Join-Path $toolkitRoot "ImgToolkitProxyInit.py"
$entryTemplatePath = Join-Path $toolkitRoot "imgToolkit.py"

if (-not (Test-Path -LiteralPath $proxyTemplatePath)) {
    throw "Missing template file: $proxyTemplatePath"
}
if (-not (Test-Path -LiteralPath $entryTemplatePath)) {
    throw "Missing template file: $entryTemplatePath"
}

$proxyTemplate = Get-Content -LiteralPath $proxyTemplatePath -Raw -Encoding UTF8
$entryTemplate = Get-Content -LiteralPath $entryTemplatePath -Raw -Encoding UTF8

$initProxy = [regex]::Replace(
    $proxyTemplate,
    '(?m)^IMG_TOOLKIT_ROOT\s*=\s*r?"[^"]*"\s*$',
    ('IMG_TOOLKIT_ROOT = r"' + $escapedToolkitRoot + '"')
)

if ($initProxy -eq $proxyTemplate) {
    throw "Failed to patch IMG_TOOLKIT_ROOT in template: $proxyTemplatePath"
}

Set-Content -Path (Join-Path $targetDir "ImgToolkitProxyInit.py") -Value $initProxy -Encoding UTF8
Set-Content -Path (Join-Path $targetDir "imgToolkit.py") -Value $entryTemplate -Encoding UTF8

Write-Host ""
Write-Host "Installed proxy files:" -ForegroundColor Green
Write-Host "  $(Join-Path $targetDir "ImgToolkitProxyInit.py")"
Write-Host "  $(Join-Path $targetDir "imgToolkit.py")"
Write-Host ""
Write-Host "Static IMG_TOOLKIT_ROOT set to: $escapedToolkitRoot"
