document.addEventListener('DOMContentLoaded', function() {
    const imageUpload = document.getElementById('image-upload');
    const displayImage = document.getElementById('display-image');
    const imageContainer = document.getElementById('image-container');
    const queryInput = document.getElementById('query-input');
    const submitQuery = document.getElementById('submit-query');
    const responseLlamaContainer = document.getElementById('response-container-llama');
    const responseLlamaText = document.getElementById('response-text-llama');
    const responseLlavaContainer = document.getElementById('response-container-llava');
    const responseLlavaText = document.getElementById('response-text-llava');
    const errorContainer = document.getElementById('error-container');
    const errorText = document.getElementById('error-text');

    // Image upload and display
    imageUpload.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                displayImage.src = e.target.result;
                imageContainer.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        }
    });

    // Submit query
    submitQuery.addEventListener('click', async () => {
        const image = imageUpload.files[0];
        const query = queryInput.value;

        if (!image || !query) {
            showError('Please upload an image and enter a query.');
            return;
        }

        const formData = new FormData();
        formData.append('image', image);
        formData.append('query', query);

        try {
            submitQuery.disabled = true;
            submitQuery.textContent = 'Processing...';
            submitQuery.classList.add('loading');

            const response = await fetch('/upload_and_query', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'An error occurred while processing your request.');
            }

            responseLlamaText.innerHTML = marked.parse(result.llama);
            responseLlamaContainer.classList.remove('hidden');

            responseLlavaText.innerHTML = marked.parse(result.llava);
            responseLlavaContainer.classList.remove('hidden');

            errorContainer.classList.add('hidden');

        } catch (error) {
            console.error('Error:', error);
            showError(error.message);
        } finally {
            submitQuery.disabled = false;
            submitQuery.textContent = 'Submit Query';
            submitQuery.classList.remove('loading');
        }
    });

    function showError(message) {
        errorText.textContent = message;
        errorContainer.classList.remove('hidden');
        responseLlamaContainer.classList.add('hidden');
        responseLlavaContainer.classList.add('hidden');
    }
});
