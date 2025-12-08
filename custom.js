function updateTimestamp() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const dateStr = now.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
    const el = document.getElementById('timestamp');
    if (el) {
        el.textContent = dateStr + ' ' + timeStr + ' EST';
    }
}
updateTimestamp();
setInterval(updateTimestamp, 1000);