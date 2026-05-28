param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

if ($Version -notmatch '^v?\d+\.\d+\.\d+$') {
    Write-Error "Invalid version: '$Version'. Please use the format e.g., 1.2.3 or v1.2.3."
    exit 1
}

$tag = if ($Version.StartsWith('v')) { $Version } else { "v$Version" }

Write-Host "Creating tag $tag..."

git tag $tag

git push origin $tag

Write-Host "Tag $tag was successfully created and pushed."
