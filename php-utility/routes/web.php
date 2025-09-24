<?php

use App\Http\Controllers\ImageEditorController;
use Illuminate\Support\Facades\Route;

Route::get('/', [ImageEditorController::class, 'index'])->name('editor.index');
Route::post('/preview', [ImageEditorController::class, 'preview'])->name('editor.preview');
Route::post('/download', [ImageEditorController::class, 'download'])->name('editor.download');
