const pw = document.getElementById("pw");
const toggle = document.getElementById("toggle");

toggle.addEventListener("click", () => {
  const show = pw.type === "password";
  pw.type = show ? "text" : "password";
  toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
});
