const msg = document.getElementById("msg");

async function post(url) {
  const r = await fetch(url, { method: "POST" });
  return r.json();
}

async function start() {
  const cfg = await (await fetch("/config")).json();
  const s = document.createElement("script");
  s.src = "https://www.paypal.com/sdk/js?client-id=" + encodeURIComponent(cfg.client_id) + "&currency=USD&intent=capture";
  s.onload = () => paypal.Buttons({
    createOrder: async () => {
      const o = await post("/api/orders");
      if (!o.id) throw new Error(o.error || "order failed");
      return o.id;
    },
    onApprove: async (data) => {
      const c = await post("/api/orders/" + data.orderID + "/capture");
      if (c.redirect) location.href = c.redirect;
      else msg.textContent = c.error || "Payment failed";
    },
    onError: () => { msg.textContent = "Checkout error. Please try again."; },
  }).render("#paypal-button");
  document.head.appendChild(s);
}

start();
