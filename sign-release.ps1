<#!
.SYNOPSIS
Signs and verifies the portable Speedometer release using a trusted certificate
already installed in the current user's Windows certificate store.

.DESCRIPTION
Smart App Control requires a code-signing certificate issued by a provider in
Microsoft's Trusted Root Program. This script never accepts or stores PFX
passwords; it signs by certificate thumbprint from Cert:\CurrentUser\My.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-fA-F0-9]{40}$')]
    [string]$CertificateThumbprint,

    [string]$FilePath = (Join-Path $PSScriptRoot 'dist\Speedometer.exe'),

    [string]$TimestampUrl = 'http://timestamp.digicert.com'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
    throw "Release file not found: $FilePath"
}

$certificate = Get-ChildItem "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
if (-not $certificate) {
    throw 'The requested certificate is not installed in Cert:\CurrentUser\My.'
}
if (-not $certificate.HasPrivateKey) {
    throw 'The requested certificate has no accessible private key.'
}
if ($certificate.NotAfter -le (Get-Date)) {
    throw "The requested certificate expired on $($certificate.NotAfter)."
}

$signtool = Get-Command 'signtool.exe' -ErrorAction SilentlyContinue
if (-not $signtool) {
    throw 'signtool.exe was not found. Install the Windows SDK Signing Tools, then run this script again.'
}

& $signtool.Source sign /sha1 $CertificateThumbprint /s My /fd SHA256 /tr $TimestampUrl /td SHA256 /v $FilePath
if ($LASTEXITCODE -ne 0) {
    throw "Signing failed with exit code $LASTEXITCODE."
}

& $signtool.Source verify /pa /all /v $FilePath
if ($LASTEXITCODE -ne 0) {
    throw "Signature verification failed with exit code $LASTEXITCODE. Do not distribute this release."
}

Write-Host "Signed and verified: $FilePath"
