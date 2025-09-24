<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        @font-face {
            font-family: 'GoudyOldStyle';
            src: url('{{ public_path('fonts/goudy-old-style-bold.ttf') }}') format('truetype');
            font-weight: 900;
            font-style: normal;
        }
        @page {
            margin: 0;
            size: {{ $imageWidth }}px {{ $imageHeight }}px;
        }
        html, body {
            width: {{ $imageWidth }}px;
            height: {{ $imageHeight }}px;
            margin: 0;
            padding: 0;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: DejaVu Sans, Arial, Helvetica, sans-serif;
        }
        .sheet {
            position: relative;
            width: {{ $imageWidth }}px;
            height: {{ $imageHeight }}px;
            page-break-after: avoid;
            page-break-inside: avoid;
        }
        .background {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        .background img {
            width: 100%;
            height: 100%;
            display: block;
        }
        .overlay-text {
            position: absolute;
            left: {{ $xPercent }}%;
            top: {{ $yPercent }}%;
            transform: translate(-50%, -50%);
            font-size: {{ $fontSize * $pdfScale }}px;
            color: {{ $textColor }};
            font-weight: 900;
            font-family: '{{ $fontFamily }}', '{{ $fontFamilyLabel }}', 'Times New Roman', serif;
            text-align: center;
            white-space: nowrap;
        }
    </style>
</head>
<body>
    <div class="sheet">
        <div class="background">
            <img src="{{ $imageDataUri }}" alt="Edited image">
        </div>
        <div class="overlay-text" style="font-weight: 900;">{{ $text }}</div>
    </div>
</body>
</html>
