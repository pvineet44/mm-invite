<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Barryvdh\DomPDF\Facade\Pdf;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class ImagePdfController extends Controller
{
    private const FONT_FAMILY = 'GoudyOldStyle';
    private const FONT_FAMILY_LABEL = 'Goudy Old Style';
    private const FONT_COLOR = '#c42526';
    private const FONT_SIZE = 45;
    private const VERTICAL_POSITION = 6.67;
    private const DEFAULT_X_POSITION = 50.0;
    private const PDF_DPI = 96;
    private const MAX_PDF_POINTS = 14400; // DomPDF ~200 inch limit

    public function generate(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'text' => ['required', 'string', 'max:255'],
            'file_name' => ['nullable', 'string', 'max:255'],
            'x_position' => ['nullable', 'numeric', 'between:0,100'],
            'y_position' => ['nullable', 'numeric', 'between:0,100'],
            'font_size' => ['nullable', 'numeric', 'between:8,200'],
            'text_color' => ['nullable', 'regex:/^#[0-9a-fA-F]{6}$/'],
        ]);

        $staticImagePath = public_path('static/static.jpg');

        if (! file_exists($staticImagePath)) {
            abort(500, 'Static background image is missing.');
        }

        [$imageWidth, $imageHeight] = $this->imageSize($staticImagePath);

        $fontSize = (float) ($validated['font_size'] ?? self::FONT_SIZE);
        $textColor = $validated['text_color'] ?? self::FONT_COLOR;
        $xPercent = isset($validated['x_position']) ? (float) $validated['x_position'] : self::DEFAULT_X_POSITION;
        $yPercent = isset($validated['y_position']) ? (float) $validated['y_position'] : self::VERTICAL_POSITION;

        $imageDataUri = $this->toDataUri($staticImagePath);

        $pdfScale = $this->pdfScale($imageWidth, $imageHeight);
        $renderDimensions = $this->scaledDimensions($imageWidth, $imageHeight, $pdfScale);
        $paper = $this->paperSizeFor($renderDimensions['width'], $renderDimensions['height']);

        $pdfHtml = view('editor.pdf', [
            'imageDataUri' => $imageDataUri,
            'text' => $validated['text'],
            'xPercent' => $xPercent,
            'yPercent' => $yPercent,
            'fontSize' => $fontSize,
            'textColor' => $textColor,
            'fontFamily' => self::FONT_FAMILY,
            'fontFamilyLabel' => self::FONT_FAMILY_LABEL,
            'imageWidth' => $renderDimensions['width'],
            'imageHeight' => $renderDimensions['height'],
            'pdfScale' => $pdfScale,
        ])->render();

        $pdfBinary = Pdf::loadHTML($pdfHtml)
            ->setPaper($paper)
            ->setOption('dpi', self::PDF_DPI)
            ->setOption('isRemoteEnabled', true)
            ->setOption('isHtml5ParserEnabled', true)
            ->output();

        $targetDirectory = realpath(base_path('../pdfs')) ?: base_path('../pdfs');

        if (! is_dir($targetDirectory) && ! mkdir($targetDirectory, 0775, true) && ! is_dir($targetDirectory)) {
            abort(500, 'Unable to prepare PDF output directory.');
        }

        $fileName = $this->desiredFileName($validated['file_name'] ?? $validated['text']);
        $relativePath = 'pdfs/' . $fileName;
        $absolutePath = rtrim($targetDirectory, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . $fileName;

        if (file_exists($absolutePath)) {
            $absolutePath = $this->uniquifyPath($absolutePath);
            $relativePath = 'pdfs/' . basename($absolutePath);
            $fileName = basename($absolutePath);
        }

        if (file_put_contents($absolutePath, $pdfBinary) === false) {
            abort(500, 'Failed to write generated PDF.');
        }

        $baseUrl = rtrim(config('app.url', url('/')), '/');
        $url = $baseUrl . '/' . $relativePath;

        return response()->json([
            'url' => $url,
            'path' => $relativePath,
        ], 201);
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

    private function paperSizeFor(float $widthPx, float $heightPx): array
    {
        return [
            0,
            0,
            $this->pixelsToPoints($widthPx),
            $this->pixelsToPoints($heightPx),
        ];
    }

    private function pixelsToPoints(float $pixels): float
    {
        return $pixels * 72 / self::PDF_DPI;
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

    private function desiredFileName(?string $input): string
    {
        $input = trim((string) $input);

        if ($input === '') {
            $input = 'invite';
        }

        $input = preg_replace('/[\\\/:*?"<>|]/', ' ', $input) ?? 'invite';
        $input = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $input) ?? $input;
        $input = preg_replace('/\s+/', ' ', $input) ?? $input;
        $input = trim($input);

        if ($input === '') {
            $input = 'invite';
        }

        if (! Str::of($input)->lower()->endsWith('.pdf')) {
            $input .= '.pdf';
        }

        return $input;
    }

    private function uniquifyPath(string $absolutePath): string
    {
        $directory = dirname($absolutePath);
        $baseName = pathinfo($absolutePath, PATHINFO_FILENAME);
        $extension = pathinfo($absolutePath, PATHINFO_EXTENSION);
        $counter = 1;

        do {
            $candidate = $directory . DIRECTORY_SEPARATOR . $baseName . ' (' . $counter . ').' . $extension;
            $counter++;
        } while (file_exists($candidate));

        return $candidate;
    }
}
