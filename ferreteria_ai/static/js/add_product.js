'use strict';

// --- Estado de la aplicación ---
let cameraStream = null;
let capturedImageBlob = null;
let imageSource = 'camera'; // 'camera' o 'file'

// --- Elementos del DOM ---
const toggleCameraBtn = document.getElementById('toggle-camera');
const toggleFileBtn = document.getElementById('toggle-file');
const cameraContainer = document.getElementById('camera-container');
const fileInputContainer = document.getElementById('file-input-container');
const cameraVideo = document.getElementById('camera-video');
const startCameraBtn = document.getElementById('start-camera-btn');
const capturePhotoBtn = document.getElementById('capture-photo-btn');
const captureCanvas = document.getElementById('capture-canvas');
const imagePreview = document.getElementById('image-preview');
const previewImg = document.getElementById('preview-img');
const removeImageBtn = document.getElementById('remove-image-btn');
const imageFileInput = document.getElementById('image-file');
const hiddenImageInput = document.getElementById('image');
const imageStatus = document.getElementById('image-status');
const productForm = document.getElementById('product-form');

// --- Funciones de Toggle ---
toggleCameraBtn.addEventListener('click', () => {
    imageSource = 'camera';
    toggleCameraBtn.classList.add('active');
    toggleFileBtn.classList.remove('active');
    cameraContainer.classList.add('active');
    fileInputContainer.classList.remove('active');
    resetImageState();
});

toggleFileBtn.addEventListener('click', () => {
    imageSource = 'file';
    toggleFileBtn.classList.add('active');
    toggleCameraBtn.classList.remove('active');
    fileInputContainer.classList.add('active');
    cameraContainer.classList.remove('active');
    stopCamera();
    resetImageState();
});

// --- Funciones de Cámara ---
startCameraBtn.addEventListener('click', async () => {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'environment',
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }, 
            audio: false 
        });
        cameraVideo.srcObject = cameraStream;
        cameraVideo.play();
        
        startCameraBtn.style.display = 'none';
        capturePhotoBtn.style.display = 'inline-block';
        
        showStatus('Cámara activada. Apunta al producto y captura la foto.', 'success');
    } catch (err) {
        console.error('Error al acceder a la cámara:', err);
        showStatus('Error al acceder a la cámara. Verifica los permisos.', 'warning');
    }
});

capturePhotoBtn.addEventListener('click', () => {
    const context = captureCanvas.getContext('2d');
    captureCanvas.width = cameraVideo.videoWidth;
    captureCanvas.height = cameraVideo.videoHeight;
    context.drawImage(cameraVideo, 0, 0, captureCanvas.width, captureCanvas.height);

    captureCanvas.toBlob((blob) => {
        capturedImageBlob = blob;
        const imageUrl = URL.createObjectURL(blob);
        previewImg.src = imageUrl;
        imagePreview.classList.add('active');

        // Crear un archivo desde el blob
        const file = new File([blob], 'captured-photo.jpg', { type: 'image/jpeg' });

        // Intentar asignar al input usando DataTransfer
        try {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            hiddenImageInput.files = dataTransfer.files;
            console.log('Archivo asignado al input:', hiddenImageInput.files.length);
        } catch (error) {
            console.error('Error al asignar archivo:', error);
        }

        stopCamera();
        showStatus('✓ Foto capturada correctamente', 'success');
    }, 'image/jpeg', 0.9);
});

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
        cameraVideo.srcObject = null;
        startCameraBtn.style.display = 'inline-block';
        capturePhotoBtn.style.display = 'none';
    }
}

// --- Funciones de Archivo ---
imageFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        console.log('Archivo seleccionado:', file.name, file.size);

        const reader = new FileReader();
        reader.onload = (event) => {
            previewImg.src = event.target.result;
            imagePreview.classList.add('active');

            // Copiar el archivo al input oculto
            try {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                hiddenImageInput.files = dataTransfer.files;
                console.log('Archivo copiado al input oculto:', hiddenImageInput.files.length);
            } catch (error) {
                console.error('Error al copiar archivo:', error);
            }

            showStatus('✓ Archivo seleccionado correctamente', 'success');
        };
        reader.readAsDataURL(file);
    }
});

// --- Función para eliminar imagen ---
removeImageBtn.addEventListener('click', () => {
    resetImageState();
    if (imageSource === 'camera') {
        showStatus('Imagen eliminada. Puedes tomar otra foto.', 'warning');
    } else {
        imageFileInput.value = '';
        showStatus('Imagen eliminada. Puedes seleccionar otro archivo.', 'warning');
    }
});

// --- Funciones auxiliares ---
function resetImageState() {
    capturedImageBlob = null;
    imagePreview.classList.remove('active');
    previewImg.src = '';
    hiddenImageInput.value = '';
    imageStatus.innerHTML = '';
    imageStatus.className = 'image-status';
}

function showStatus(message, type) {
    imageStatus.innerHTML = message;
    imageStatus.className = `image-status ${type}`;
}

// --- Validación y envío del formulario ---
let isSubmitting = false;

productForm.addEventListener('submit', async (e) => {
    e.preventDefault(); // Siempre prevenir el envío por defecto

    console.log('Formulario enviado, isSubmitting:', isSubmitting);

    // Evitar múltiples envíos
    if (isSubmitting) {
        console.log('Ya se está enviando, ignorando...');
        return false;
    }

    console.log('Archivos en input oculto:', hiddenImageInput.files.length);
    console.log('Blob capturado:', capturedImageBlob);

    // Verificar si hay un archivo en el input o un blob capturado
    const hasFile = hiddenImageInput.files && hiddenImageInput.files.length > 0;
    const hasBlob = capturedImageBlob !== null;

    if (!hasFile && !hasBlob) {
        showStatus('⚠️ Debes capturar o seleccionar una imagen antes de guardar', 'warning');
        return false;
    }

    // Marcar como enviando
    isSubmitting = true;
    showStatus('Guardando producto...', 'success');

    // Crear FormData manualmente
    const formData = new FormData();
    formData.append('name', document.getElementById('name').value);
    formData.append('code', document.getElementById('code').value);
    formData.append('category', document.getElementById('category').value);
    formData.append('description', document.getElementById('description').value);
    formData.append('stock', document.getElementById('stock').value);
    formData.append('price', document.getElementById('price').value);

    // Agregar la imagen (blob o archivo)
    if (hasBlob) {
        console.log('Agregando blob al FormData');
        formData.append('image', capturedImageBlob, 'captured-photo.jpg');
    } else if (hasFile) {
        console.log('Agregando archivo al FormData');
        formData.append('image', hiddenImageInput.files[0]);
    }

    try {
        // Enviar el formulario usando fetch
        const response = await fetch('/products', {
            method: 'POST',
            body: formData
        });

        console.log('Respuesta del servidor:', response.status);

        if (response.ok || response.status === 303) {
            // Redirigir a la página de productos
            window.location.href = '/products/new';
        } else {
            const errorText = await response.text();
            console.error('Error del servidor:', errorText);
            showStatus('⚠️ Error al guardar el producto. Revisa la consola.', 'warning');
            isSubmitting = false;
        }
    } catch (error) {
        console.error('Error al enviar formulario:', error);
        showStatus('⚠️ Error de conexión con el servidor', 'warning');
        isSubmitting = false;
    }
});

// --- Limpiar al salir ---
window.addEventListener('beforeunload', () => {
    stopCamera();
});

// --- Importación masiva desde Excel ---
const toggleImportBtn = document.getElementById('toggle-import-btn');
const importSection = document.getElementById('import-section');
const importForm = document.getElementById('import-form');
const importResult = document.getElementById('import-result');

// Toggle de la sección de importación
toggleImportBtn.addEventListener('click', () => {
    if (importSection.style.display === 'none' || importSection.style.display === '') {
        importSection.classList.add('active');
        toggleImportBtn.innerHTML = '<span style="font-size: 1.5rem;">❌</span><span>Cerrar Importación</span>';
    } else {
        importSection.classList.remove('active');
        toggleImportBtn.innerHTML = '<span style="font-size: 1.5rem;">📊</span><span>Importación Masiva</span>';
        importResult.innerHTML = '';
    }
});

// Mostrar nombre del archivo seleccionado
const excelFileInput = document.getElementById('excel-file');
excelFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        console.log('Archivo Excel seleccionado:', file.name, file.size);
        const wrapper = excelFileInput.closest('.file-input-wrapper');
        const uploadIcon = wrapper.querySelector('.upload-icon');
        const firstP = wrapper.querySelector('p:first-of-type');

        uploadIcon.textContent = '✅';
        firstP.innerHTML = `<strong style="color: #28a745;">Archivo seleccionado: ${file.name}</strong>`;
    }
});

// Manejar envío del formulario de importación
importForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById('excel-file');
    const file = fileInput.files[0];

    console.log('Submit del formulario de importación');
    console.log('FileInput:', fileInput);
    console.log('Archivo seleccionado:', file);

    if (!file) {
        showImportResult('Por favor selecciona un archivo Excel', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('excel_file', file);

    console.log('FormData creado, archivo agregado:', file.name);

    // Mostrar loading
    showImportResult('Procesando archivo...', 'loading');

    try {
        const response = await fetch('/products/import', {
            method: 'POST',
            body: formData
        });

        console.log('Respuesta del servidor:', response.status, response.statusText);

        let data;
        try {
            data = await response.json();
            console.log('Data recibida:', data);
        } catch (jsonError) {
            console.error('Error al parsear JSON:', jsonError);
            showImportResult('Error: La respuesta del servidor no es válida', 'error');
            return;
        }

        if (response.ok && data.success) {
            let message = `
                <div style="color: green; font-weight: bold;">
                    ✓ Importación completada
                </div>
                <p>Productos importados: <strong>${data.imported}</strong></p>
                <p>Productos omitidos: <strong>${data.skipped}</strong></p>
            `;

            if (data.errors && data.errors.length > 0) {
                message += `
                    <details style="margin-top: 1rem;">
                        <summary style="cursor: pointer; color: var(--danger-color);">
                            Ver errores (${data.errors.length})
                        </summary>
                        <ul style="margin-top: 0.5rem; font-size: 0.9rem;">
                            ${data.errors.map(err => `<li>${err}</li>`).join('')}
                        </ul>
                    </details>
                `;
            }

            message += `
                <p style="margin-top: 1rem;">
                    <a href="/products" class="btn btn-primary">Ver productos importados</a>
                </p>
            `;

            showImportResult(message, 'success');
            fileInput.value = '';
        } else {
            // Mostrar el mensaje de error detallado del servidor
            const errorMsg = data.error || data.detail || 'Error desconocido';
            showImportResult(`<strong>Error:</strong> ${errorMsg}`, 'error');
        }
    } catch (error) {
        console.error('Error al importar:', error);
        showImportResult(`Error de conexión: ${error.message}`, 'error');
    }
});

function showImportResult(message, type) {
    const colors = {
        'success': '#d4edda',
        'error': '#f8d7da',
        'loading': '#fff3cd'
    };

    const textColors = {
        'success': '#155724',
        'error': '#721c24',
        'loading': '#856404'
    };

    importResult.innerHTML = `
        <div style="
            padding: 1rem;
            border-radius: 6px;
            background-color: ${colors[type] || colors['loading']};
            color: ${textColors[type] || textColors['loading']};
            border: 1px solid ${textColors[type] || textColors['loading']};
        ">
            ${message}
        </div>
    `;
}

