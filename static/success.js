/* copy the public proof link (works after the record strip is refreshed) */
document.addEventListener("click", async (e) => {
  const b = e.target.closest("#sharebtn");
  if (!b) return;
  const label = b.lastChild;
  try { await navigator.clipboard.writeText(location.origin + b.dataset.url); label.textContent = "Link copied"; }
  catch (err) { label.textContent = "Copy: " + location.origin + b.dataset.url; }
  setTimeout(() => { label.textContent = "Share proof link"; }, 2500);
});

/* after a download click: say what happened, then refresh the delivery record from the server */
const dl = document.getElementById("download");
const note = document.getElementById("dlnote");
dl.addEventListener("click", () => {
  note.textContent = "Your download has started. Look in your browser's Downloads folder.";
  setTimeout(async () => {
    try {
      const html = new DOMParser().parseFromString(await (await fetch(location.href)).text(), "text/html");
      const fresh = html.querySelector(".strip");
      if (fresh) document.querySelector(".strip").replaceWith(fresh);
    } catch (e) { /* the record refreshes on the next visit */ }
  }, 900);
});
