param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Runtime.WindowsRuntime

[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null

$asTaskOperation = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq "AsTask" -and
        $_.IsGenericMethod -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1"
    } |
    Select-Object -First 1

if ($null -eq $asTaskOperation) {
    throw "Unable to locate the WinRT AsTask adapter."
}

function Await-Operation {
    param(
        [Parameter(Mandatory = $true)]
        $Operation,
        [Parameter(Mandatory = $true)]
        [Type]$ResultType
    )

    $method = $asTaskOperation.MakeGenericMethod($ResultType)
    $task = $method.Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    throw "Windows OCR engine is unavailable. Install a Chinese OCR language feature first."
}

$fullPath = (Resolve-Path -LiteralPath $ImagePath).Path
$file = Await-Operation (
    [Windows.Storage.StorageFile]::GetFileFromPathAsync($fullPath)
) ([Windows.Storage.StorageFile])
$stream = Await-Operation (
    $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await-Operation (
    [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await-Operation (
    $decoder.GetSoftwareBitmapAsync()
) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await-Operation (
    $engine.RecognizeAsync($bitmap)
) ([Windows.Media.Ocr.OcrResult])

$lines = foreach ($line in $result.Lines) {
    $wordBoxes = @($line.Words)
    $bbox = $null
    if ($wordBoxes.Count -gt 0) {
        $x1 = ($wordBoxes | ForEach-Object { $_.BoundingRect.X } | Measure-Object -Minimum).Minimum
        $y1 = ($wordBoxes | ForEach-Object { $_.BoundingRect.Y } | Measure-Object -Minimum).Minimum
        $x2 = ($wordBoxes | ForEach-Object {
            $_.BoundingRect.X + $_.BoundingRect.Width
        } | Measure-Object -Maximum).Maximum
        $y2 = ($wordBoxes | ForEach-Object {
            $_.BoundingRect.Y + $_.BoundingRect.Height
        } | Measure-Object -Maximum).Maximum
        $bbox = @(
            @($x1, $y1),
            @($x2, $y1),
            @($x2, $y2),
            @($x1, $y2)
        )
    }
    [PSCustomObject]@{
        text = $line.Text
        confidence = 1.0
        bbox = $bbox
        words = @($wordBoxes | ForEach-Object {
            $rect = $_.BoundingRect
            [PSCustomObject]@{
                text = $_.Text
                x = $rect.X
                y = $rect.Y
                width = $rect.Width
                height = $rect.Height
            }
        })
    }
}

$payload = [PSCustomObject]@{
    engine = "Windows.Media.Ocr"
    language = $engine.RecognizerLanguage.LanguageTag
    lines = @($lines)
}

$json = $payload | ConvertTo-Json -Depth 8
if ($OutputPath) {
    $json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
} else {
    $json
}
