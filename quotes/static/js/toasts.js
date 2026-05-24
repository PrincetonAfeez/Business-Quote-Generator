(() => {
  const stack = () => document.getElementById("toast-stack");

  const renderToast = ({ message, level = "info" }) => {
    const target = stack();
    if (!target || !message) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${level}`;
    toast.setAttribute("role", "status");
    toast.textContent = message;
    target.appendChild(toast);

    window.setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-4px)";
      toast.style.transition = "opacity 160ms ease, transform 160ms ease";
      window.setTimeout(() => toast.remove(), 180);
    }, 3500);
  };

  document.body.addEventListener("show-toast", (event) => {
    renderToast(event.detail || {});
  });

  document.body.addEventListener("htmx:afterSwap", () => {
    if (window.lucide) window.lucide.createIcons();
  });
})();
