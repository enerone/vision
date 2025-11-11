'use strict';

// --- Estado de la Aplicación ---
let shoppingList = [];

// --- Obtener elementos del DOM ---
const video = document.getElementById('video');
const captureBtn = document.getElementById('capture-btn');
const canvas = document.getElementById('canvas');
const resultContainer = document.getElementById('result-container');
const spinner = document.getElementById('spinner');
const shoppingListSection = document.getElementById('shopping-list-section');
const shoppingListContainer = document.getElementById('shopping-list-container');
const clearListBtn = document.getElementById('clear-list-btn');
const frozenFrame = document.getElementById('frozen-frame');

// --- Lógica del Carrito de Compras ---

function renderShoppingList() {
    shoppingListContainer.innerHTML = '';
    let grandTotal = 0;

    if (shoppingList.length === 0) {
        shoppingListSection.style.display = 'none';
        const totalContainer = document.getElementById('grand-total-container');
        if(totalContainer) totalContainer.innerHTML = '';
        return;
    }

    shoppingListSection.style.display = 'block';

    shoppingList.forEach((item, index) => {
        const itemTotal = item.price * item.quantity;
        grandTotal += itemTotal;

        const listItem = document.createElement('div');
        listItem.classList.add('shopping-list-item');
        listItem.innerHTML = `
            <div class="item-details">
                ${item.name}
                <span class="code">${item.description || item.code}</span>
            </div>
            <div class="item-controls">
                <div class="item-price">${item.price.toFixed(2)}/u</div>
                <input type="number" class="quantity-input" value="${item.quantity}" min="1" data-index="${index}">
                <div class="item-price"><strong>${itemTotal.toFixed(2)}</strong></div>
                <button class="remove-item-btn" data-index="${index}" title="Eliminar item">&times;</button>
            </div>
        `;
        shoppingListContainer.appendChild(listItem);
    });

    let totalContainer = document.getElementById('grand-total-container');
    if (!totalContainer) {
        totalContainer = document.createElement('div');
        totalContainer.id = 'grand-total-container';
        shoppingListSection.appendChild(totalContainer);
    }
    totalContainer.innerHTML = `Total: <strong>${grandTotal.toFixed(2)}</strong>`;

    document.querySelectorAll('.quantity-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const index = parseInt(e.target.dataset.index, 10);
            const newQuantity = parseInt(e.target.value, 10);
            if (newQuantity > 0) {
                shoppingList[index].quantity = newQuantity;
            }
            renderShoppingList();
        });
    });

    document.querySelectorAll('.remove-item-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const indexToRemove = parseInt(e.target.dataset.index, 10);
            shoppingList.splice(indexToRemove, 1);
            renderShoppingList();
        });
    });
}

function addToShoppingList(product) {
    const existingItem = shoppingList.find(item => item.code === product.code);
    if (existingItem) {
        existingItem.quantity++;
    } else {
        shoppingList.push({
            name: product.name,
            code: product.code,
            description: product.description,
            price: product.price,
            quantity: 1,
        });
    }
    renderShoppingList();
}

clearListBtn.addEventListener('click', () => {
    shoppingList = [];
    renderShoppingList();
});


// --- Lógica de la Cámara y Captura ---

async function setupCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
        video.srcObject = stream;
        video.play();
    } catch (err) {
        resultContainer.innerHTML = `<p style="color: var(--danger-color);">Error al acceder a la cámara.</p>`;
        captureBtn.disabled = true;
    }
}

captureBtn.addEventListener('click', async () => {
    captureBtn.disabled = true;
    spinner.style.display = 'block';
    resultContainer.innerHTML = '';

    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Congelar la imagen
    const frameDataUrl = canvas.toDataURL('image/jpeg');
    frozenFrame.src = frameDataUrl;
    video.style.display = 'none';
    frozenFrame.style.display = 'block';

    canvas.toBlob(async (blob) => {
        const formData = new FormData();
        formData.append('image', blob, 'capture.jpg');

        try {
            const response = await fetch('/api/identify', { method: 'POST', body: formData });
            const data = await response.json();

            if (response.ok) {
                if (data.matches && data.matches.length > 1) {
                    displayMultipleMatches(data.matches);
                } else if (data.matches && data.matches.length === 1) {
                    displaySingleMatch(data.matches[0]);
                } else {
                     resultContainer.innerHTML = `<p>No se encontraron coincidencias.</p>`;
                }
            } else {
                resultContainer.innerHTML = `<p>${data.identification || data.error || 'Error desconocido.'}</p>`;
            }
        } catch (error) {
            resultContainer.innerHTML = `<p style="color: var(--danger-color);">Error de conexión con el servidor.</p>`;
        } finally {
            captureBtn.disabled = false;
            spinner.style.display = 'none';
            // Descongelar la imagen y volver al video en vivo
            setTimeout(() => {
                video.style.display = 'block';
                frozenFrame.style.display = 'none';
            }, 1500); // Pequeño retraso para que el usuario vea el resultado con la imagen congelada
        }
    }, 'image/jpeg');
});

function displaySingleMatch(match) {
    const product = match.product;
    resultContainer.innerHTML = `<h3 style="text-align: center;">Añadido a la lista: ${product.name}</h3>`;
    addToShoppingList(product);
}

function displayMultipleMatches(matches) {
    let html = `<h3>Se encontraron varios resultados. Selecciona el correcto:</h3>`;
    html += `<div class="card-grid">`;
    matches.forEach((match, index) => {
        const product = match.product;
        html += `
            <div class="card choice-card" data-match-index="${index}">
                <img src="${product.image_path}" alt="${product.name}" class="card-image">
                <div class="card-content">
                    <h3>${product.name}</h3>
                    <p class="code">Código: ${product.code}</p>
                    <p><strong>Similitud:</strong> ${match.similarity_score.toFixed(2)}</p>
                </div>
            </div>
        `;
    });
    html += `</div>`;
    resultContainer.innerHTML = html;

    document.querySelectorAll('.choice-card').forEach(card => {
        card.addEventListener('click', (e) => {
            const matchIndex = parseInt(e.currentTarget.dataset.matchIndex, 10);
            const selectedMatch = matches[matchIndex];
            displaySingleMatch(selectedMatch);
        });
    });
}

// --- Iniciar todo ---
setupCamera();
renderShoppingList();
