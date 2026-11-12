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
