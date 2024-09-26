// main.js
document.querySelector('form').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the form from submitting traditionally

    const formData = new FormData(this);

    fetch('/generate_story', {
        method: 'POST',
        body: formData,
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('output-story').textContent = data.story;
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('output-story').textContent = 'An error occurred. Please try again.';
    });
});
