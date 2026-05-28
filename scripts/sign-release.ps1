param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [Parameter(Mandatory = $true)]
    [string]$CertificateBase64,

    [Parameter(Mandatory = $true)]
    [string]$CertificatePassword
)

if (-not (Test-Path $FilePath)) {
    throw "File not found: $FilePath"
}

$tempPfx = Join-Path $env:TEMP "nano-clicker-signing.pfx"

[System.IO.File]::WriteAllBytes($tempPfx, [Convert]::FromBase64String($CertificateBase64))

try {
    & signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f $tempPfx /p $CertificatePassword $FilePath
    if ($LASTEXITCODE -ne 0) {
        throw "signtool failed with exit code $LASTEXITCODE"
    }

    & signtool.exe verify /pa /v $FilePath
    if ($LASTEXITCODE -ne 0) {
        throw "signtool verification failed with exit code $LASTEXITCODE"
    }

    Write-Host "Signed and verified: $FilePath"
}
finally {
    if (Test-Path $tempPfx) {
        Remove-Item $tempPfx -Force
    }
}
