<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Preview | Image Text Overlay</title>
    <style>
        @font-face {
            font-family: 'GoudyOldStyle';
            src: url('{{ asset('fonts/goudy-old-style-bold.ttf') }}') format('truetype');
            font-weight: 900;
            font-style: normal;
        }
        body {
            font-family: Arial, sans-serif;
            margin: 2rem;
            color: #1f2937;
            background-color: #f3f4f6;
        }
        .container {
            max-width: 960px;
            margin: 0 auto;
            background: #ffffff;
            padding: 2rem;
            border-radius: 0.5rem;
            box-shadow: 0 20px 40px rgba(15, 23, 42, 0.12);
        }
        h1 {
            margin-bottom: 1rem;
            font-size: 1.75rem;
            color: #111827;
        }
        p {
            margin-top: 0;
        }
        .meta {
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
            margin-bottom: 1.5rem;
            color: #6b7280;
        }
        .canvas-wrapper {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            align-items: center;
        }
        .canvas {
            position: relative;
            margin: 0 auto;
            border-radius: 0.75rem;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
        }
        .canvas img {
            width: 100%;
            display: block;
        }
        .overlay-text {
            position: absolute;
            transform: translate(-50%, -50%);
            font-weight: 900;
            white-space: nowrap;
            text-align: center;
        }
        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-top: 2rem;
        }
        button,
        .link-button {
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            border: none;
            font-size: 1rem;
            cursor: pointer;
            text-decoration: none;
        }
        button {
            background-color: #2563eb;
            color: #ffffff;
        }
        button:hover {
            background-color: #1d4ed8;
        }
        .link-button {
            background-color: #e5e7eb;
            color: #111827;
        }
        .link-button:hover {
            background-color: #d1d5db;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Preview your layout</h1>
        <p>Review the placement before exporting to PDF. If something looks off, use your browser's back button to tweak the inputs.</p>
        <div class="meta">
            <span><strong>Image size:</strong> {{ $imageDimensions['width'] }} × {{ $imageDimensions['height'] }} px</span>
            <span><strong>Text:</strong> {{ $text }}</span>
            <span><strong>Position:</strong> {{ $xPercent }}% / {{ $yPercent }}%</span>
            <span><strong>Font:</strong> {{ $fontFamilyLabel }} bold, {{ $fontSize }} px, {{ $textColor }}</span>
            <span><strong>Preview scale:</strong> 50% ({{ $previewDimensions['width'] }} × {{ $previewDimensions['height'] }} px)</span>
        </div>
        <div class="canvas-wrapper">
            <div
                class="canvas"
                style="width: {{ $previewDimensions['width'] }}px; height: {{ $previewDimensions['height'] }}px;"
            >
                <img src="{{ $imageUrl }}" alt="Preview image" style="width: 100%; height: 100%;">
                <div
                    class="overlay-text"
                    style="left: {{ $xPercent }}%; top: {{ $yPercent }}%; font-size: {{ $fontSize * $previewDimensions['scale'] }}px; color: {{ $textColor }}; font-weight: 900; font-family: '{{ $fontFamily }}', '{{ $fontFamilyLabel }}', 'Times New Roman', serif;"
                >{{ $text }}</div>
            </div>
        </div>
        <form class="actions" method="POST" action="{{ route('editor.download') }}">
            @csrf
            <input type="hidden" name="image_path" value="{{ $imagePath }}">
            <input type="hidden" name="text" value="{{ $text }}">
            <input type="hidden" name="x_position" value="{{ $xPercent }}">
            <button type="submit">Download PDF</button>
            <a class="link-button" href="{{ route('editor.index') }}">Start over</a>
        </form>
    </div>
</body>
</html>
