<?php

use App\Http\Controllers\Api\ImagePdfController;
use Illuminate\Support\Facades\Route;

Route::post('/generate-pdf', [ImagePdfController::class, 'generate']);
