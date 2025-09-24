<?php

namespace App\Http\Controllers;

use Barryvdh\DomPDF\Facade\Pdf;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Illuminate\View\View;

class ImageEditorController extends Controller
{
    private const FONT_FAMILY = 'GoudyOldStyle';
    private const FONT_FAMILY_LABEL = 'Goudy Old Style';
    private const FONT_COLOR = '#c42526';
    private const FONT_SIZE = 45;
    private const VERTICAL_POSITION = 6.67;
    private const PDF_DPI = 96;
    private const MAX_PDF_POINTS = 14400; // DomPDF ~200 inch limit

    public function index(): View
    {
        return view('editor.index');
    }

    public function preview(Request $request): View
    {
        $validated = $request->validate([
            'image' => ['required', 'image', 'mimes:jpeg,jpg'],
            'text' => ['required', 'string', 'max:255'],
            'x_position' => ['required', 'numeric', 'between:0,100'],
        ]);

        $fontSize = self::FONT_SIZE;
        $textColor = self::FONT_COLOR;
        $fontFamily = self::FONT_FAMILY;
        $fontFamilyLabel = self::FONT_FAMILY_LABEL;
        $yPercent = self::VERTICAL_POSITION;

        $relativePath = $request->file('image')->store('uploads', 'public');

        $absolutePath = Storage::disk('public')->path($relativePath);

        [$imageWidth, $imageHeight] = $this->imageSize($absolutePath);
        $previewScale = 0.5;
        $previewDimensions = $this->scaledDimensions($imageWidth, $imageHeight, $previewScale);

        return view('editor.preview', [
            'imageUrl' => Storage::url($relativePath),
            'imagePath' => $relativePath,
            'text' => $validated['text'],
            'xPercent' => $validated['x_position'],
            'yPercent' => $yPercent,
            'fontSize' => $fontSize,
            'textColor' => $textColor,
            'fontFamily' => $fontFamily,
            'fontFamilyLabel' => $fontFamilyLabel,
            'imageDimensions' => [
                'width' => $imageWidth,
                'height' => $imageHeight,
            ],
            'previewDimensions' => $previewDimensions,
        ]);
    }

    public function download(Request $request)
    {
        $validated = $request->validate([
            'image_path' => ['required', 'string'],
            'text' => ['required', 'string', 'max:255'],
            'x_position' => ['required', 'numeric', 'between:0,100'],
        ]);

        $imagePath = ltrim($validated['image_path'], '/');

        if (!Storage::disk('public')->exists($imagePath)) {
            return redirect()
                ->route('editor.index')
                ->withErrors(['image' => 'Unable to locate the uploaded image. Please try again.']);
        }

        $absolutePath = Storage::disk('public')->path($imagePath);
        [$imageWidth, $imageHeight] = $this->imageSize($absolutePath);

        $fontSize = self::FONT_SIZE;
        $textColor = self::FONT_COLOR;
        $fontFamily = self::FONT_FAMILY;
        $fontFamilyLabel = self::FONT_FAMILY_LABEL;
        $yPercent = self::VERTICAL_POSITION;

        $imageDataUri = $this->toDataUri($absolutePath);

        $pdfScale = $this->pdfScale($imageWidth, $imageHeight);
        $renderDimensions = $this->scaledDimensions($imageWidth, $imageHeight, $pdfScale);

        $paper = $this->paperSizeFor($renderDimensions['width'], $renderDimensions['height']);

        $pdfHtml = view('editor.pdf', [
            'imageDataUri' => $imageDataUri,
            'text' => $validated['text'],
            'xPercent' => $validated['x_position'],
            'yPercent' => $yPercent,
            'fontSize' => $fontSize,
            'textColor' => $textColor,
            'fontFamily' => $fontFamily,
            'fontFamilyLabel' => $fontFamilyLabel,
            'imageWidth' => $renderDimensions['width'],
            'imageHeight' => $renderDimensions['height'],
            'pdfScale' => $pdfScale,
        ])->render();

        return Pdf::loadHTML($pdfHtml)
            ->setPaper($paper)
            ->setOption('dpi', self::PDF_DPI)
            ->setOption('isRemoteEnabled', true)
            ->setOption('isHtml5ParserEnabled', true)
            ->download('edited-image.pdf');
    }

    private function paperSizeFor(int $widthPx, int $heightPx): array
    {
        return [
            0,
            0,
            $this->pixelsToPoints($widthPx),
            $this->pixelsToPoints($heightPx),
        ];
    }

    private function pixelsToPoints(float|int $pixels): float
    {
        return $pixels * 72 / self::PDF_DPI;
    }

    private function imageSize(string $absolutePath): array
    {
        $info = @getimagesize($absolutePath);

        if (! $info || ! isset($info[0], $info[1])) {
            return [
                (int) round(595.28 * self::PDF_DPI / 72),
                (int) round(841.89 * self::PDF_DPI / 72),
            ];
        }

        return [$info[0], $info[1]];
    }

    private function scaledDimensions(int $widthPx, int $heightPx, float $scale): array
    {
        return [
            'width' => max(1, (int) round($widthPx * $scale)),
            'height' => max(1, (int) round($heightPx * $scale)),
            'scale' => $scale,
        ];
    }

    private function pdfScale(int $widthPx, int $heightPx): float
    {
        $widthPoints = $this->pixelsToPoints($widthPx);
        $heightPoints = $this->pixelsToPoints($heightPx);

        $maxDimension = max($widthPoints, $heightPoints);

        if ($maxDimension <= self::MAX_PDF_POINTS) {
            return 1.0;
        }

        $scale = self::MAX_PDF_POINTS / $maxDimension;

        return max(0.01, round($scale, 4));
    }

    private function toDataUri(string $absolutePath): string
    {
        ini_set('memory_limit', '1024M');

        $contents = file_get_contents($absolutePath);
        $extension = $this->guessExtension($absolutePath);

        return sprintf('data:image/%s;base64,%s', $extension, base64_encode($contents));
    }

    private function guessExtension(string $absolutePath): string
    {
        $mime = mime_content_type($absolutePath) ?: 'image/jpeg';

        return match ($mime) {
            'image/png' => 'png',
            'image/webp' => 'webp',
            default => 'jpeg',
        };
    }
}
