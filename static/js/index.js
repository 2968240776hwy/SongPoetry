// static/js/index.js
document.addEventListener('DOMContentLoaded', function () {
    const poemCarousel = new bootstrap.Carousel(document.getElementById('poemCarousel'), {
        interval: 5000,
        wrap: true
    });
});