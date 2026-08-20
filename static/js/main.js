// main.js — students will add JavaScript here as features are built

(function () {
    var trigger = document.getElementById('how-it-works-trigger');
    var modal = document.getElementById('how-it-works-modal');
    if (!trigger || !modal) return;

    var closeBtn = document.getElementById('how-it-works-modal-close');
    var iframe = document.getElementById('how-it-works-video');
    var videoSrc = iframe.getAttribute('data-src');

    function openModal() {
        iframe.setAttribute('src', videoSrc + '?autoplay=1&rel=0');
        modal.classList.add('is-open');
    }

    function closeModal() {
        modal.classList.remove('is-open');
        iframe.setAttribute('src', '');
    }

    trigger.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);

    modal.addEventListener('click', function (event) {
        if (event.target === modal) closeModal();
    });
})();
