'use strict';

// --- Estado de la aplicación ---
let cameraStream = null;
let capturedImageBlob = null;
let imageSource = 'keep'; // 'keep', 'camera' o 'file'

// --- Elementos del DOM ---
const toggleKeepBtn = document.getElementById('toggle-keep');
const toggleCameraBtn = document.getElementById('toggle-camera');
const toggleFileBtn = document.getElementById('toggle-file');
const keepCurrentOption = document.getElementById('keep-current-option');
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
toggleKeepBtn.addEventListener('click', () => {
    imageSource = 'keep';
    toggleKeepBtn.classList.add('active');
    toggleCameraBtn.classList.remove('active');
    toggleFileBtn.classList.remove('active');
    keepCurrentOption.classList.add('active');
    cameraContainer.classList.remove('active');
    fileInputContainer.classList.remove('active');
    stopCamera();
    resetImageState();
    showStatus('Se mantendrá la imagen actual', 'success');
});

toggleCameraBtn.addEventListener('click', () => {
    imageSource = 'camera';
    toggleCameraBtn.classList.add('active');
    toggleKeepBtn.classList.remove('active');
    toggleFileBtn.classList.remove('active');
    cameraContainer.classList.add('active');
    keepCurrentOption.classList.remove('active');
    fileInputContainer.classList.remove('active');
    resetImageState();
});

toggleFileBtn.addEventListener('click', () => {
    imageSource = 'file';
    toggleFileBtn.classList.add('active');
    toggleKeepBtn.classList.remove('active');
    toggleCameraBtn.classList.remove('active');
    fileInputContainer.classList.add('active');
    keepCurrentOption.classList.remove('active');
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
        showStatus('✓ Foto capturada correctamente. Se reemplazará la imagen actual.', 'success');
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

            showStatus('✓ Archivo seleccionado correctamente. Se reemplazará la imagen actual.', 'success');
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

// --- Inicialización ---
// Por defecto, mantener la imagen actual
toggleKeepBtn.classList.add('active');
keepCurrentOption.classList.add('active');

// --- Limpiar al salir ---
window.addEventListener('beforeunload', () => {
    stopCamera();
});
