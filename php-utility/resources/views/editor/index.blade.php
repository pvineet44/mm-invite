<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Text Overlay</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 2rem;
            color: #1f2937;
            background-color: #f9fafb;
        }
        .container {
            max-width: 720px;
            margin: 0 auto;
            background: #ffffff;
            padding: 2rem;
            border-radius: 0.5rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
        }
        h1 {
            margin-bottom: 1.5rem;
            font-size: 1.75rem;
            color: #111827;
        }
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 0.4rem;
        }
        input[type="number"],
        input[type="color"],
        input[type="file"],
        textarea,
        button {
            width: 100%;
            padding: 0.65rem;
            border-radius: 0.375rem;
            border: 1px solid #d1d5db;
            font-size: 1rem;
        }
        input[type="color"] {
            padding: 0.2rem;
            height: 2.75rem;
        }
        input[type="file"] {
            padding: 0.35rem 0.65rem;
        }
        .field {
            margin-bottom: 1.15rem;
        }
        .help {
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 0.25rem;
        }
        button {
            background-color: #2563eb;
            color: #ffffff;
            border: none;
            cursor: pointer;
            transition: background-color 0.15s ease;
        }
        button:hover {
            background-color: #1d4ed8;
        }
        .errors {
            background-color: #fee2e2;
            border: 1px solid #f87171;
            color: #7f1d1d;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
        }
        .errors ul {
            list-style: disc;
            padding-left: 1.25rem;
            margin: 0.5rem 0 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Add Text To Your Image</h1>
        @if ($errors->any())
            <div class="errors">
                <strong>We found a few issues:</strong>
                <ul>
                    @foreach ($errors->all() as $error)
                        <li>{{ $error }}</li>
                    @endforeach
                </ul>
            </div>
        @endif
        <form method="POST" action="{{ route('editor.preview') }}" enctype="multipart/form-data">
            @csrf
            <div class="field">
                <label for="image">JPEG image</label>
                <input id="image" name="image" type="file" accept="image/jpeg" required>
                <p class="help">Upload the background JPEG you want to place text on; large files will be optimised automatically.</p>
            </div>
            <div class="field">
                <label for="text">Overlay text</label>
                <textarea id="text" name="text" rows="3" placeholder="e.g. Welcome to the event" required>{{ old('text') }}</textarea>
            </div>
            <div class="field">
                <label for="x_position">Horizontal position (%)</label>
                <input id="x_position" name="x_position" type="number" min="0" max="100" value="{{ old('x_position', 50) }}" required>
                <p class="help">0 is the far left, 100 is the far right edge of the image.</p>
            </div>
            <input type="hidden" name="y_position" value="6.67">
            <input type="hidden" name="font_size" value="24">
            <input type="hidden" name="text_color" value="#c42526">
            <p class="help">Text will render in Goudy Old Style bold, 45px, at 6.67% from the top.</p>
            <button type="submit">Preview layout</button>
        </form>
    </div>
</body>
</html>
