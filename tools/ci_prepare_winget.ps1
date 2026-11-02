# Hosted runners can omit App Installer or the default PowerShell repository.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'This bootstrap is only for disposable GitHub runners.' }
Install-PackageProvider -Name NuGet -Force | Out-Null
for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
        if (-not (Get-PSRepository -Name PSGallery -ErrorAction SilentlyContinue)) {
            Register-PSRepository -Default
        }
        Install-Module -Name Microsoft.WinGet.Client -Force -Repository PSGallery
        Repair-WinGetPackageManager -AllUsers
        break
    } catch {
        if ($attempt -eq 3) { throw }
        Write-Warning "WinGet bootstrap retry $attempt : $_"
        Start-Sleep -Seconds 5
    }
}
$apps = $env:LOCALAPPDATA + '\Microsoft\WindowsApps'
$apps | Out-File -FilePath $env:GITHUB_PATH -Append -Encoding utf8
& "$apps\winget.exe" --version
if ($LASTEXITCODE -ne 0) { throw 'WinGet did not start after installation.' }
