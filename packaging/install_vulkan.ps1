$ErrorActionPreference = 'Stop'
$version = '1.4.363.0'
$expected = '94a82d378f7a5e3e54c9db7d2fb7016af136e14ac0a18dbf0f2f67a36352d141'
$installer = Join-Path $env:RUNNER_TEMP 'vulkan-sdk.exe'
$root = Join-Path $env:RUNNER_TEMP "VulkanSDK\$version"
Invoke-WebRequest "https://sdk.lunarg.com/sdk/download/$version/windows/vulkansdk-windows-X64-$version.exe" -OutFile $installer
if ((Get-FileHash $installer -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw 'Vulkan SDK checksum mismatch' }
$process = Start-Process $installer -ArgumentList @('--root', $root, '--accept-licenses', '--default-answer', '--confirm-command', 'install', 'copy_only=1') -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Vulkan SDK installer failed: $($process.ExitCode)" }
if (!(Test-Path "$root\Bin\glslc.exe")) { throw 'Vulkan shader compiler missing' }
"VULKAN_SDK=$root" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"$root\Bin" | Out-File -FilePath $env:GITHUB_PATH -Append -Encoding utf8
