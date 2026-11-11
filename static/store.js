const msg = document.getElementById("msg");

async function post(url) {
  const r = await fetch(url, { method: "POST" });
  return r.json();
}

async function start() {
  const cfg = await (await fetch("/config")).json();
  const s = document.createElement("script");
  // Only the PayPal button: cards, credit, pay later and Venmo are switched off
  s.src = "https://www.paypal.com/sdk/js?client-id=" + encodeURIComponent(cfg.client_id) + "&currency=USD&intent=capture&disable-funding=card,credit,paylater,venmo";
  s.onload = () => paypal.Buttons({
    fundingSource: paypal.FUNDING.PAYPAL,
    style: { layout: "horizontal", color: "blue", shape: "rect", label: "paypal", height: 48, tagline: false },
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
  s.onerror = () => { msg.textContent = "PayPal could not load. Check your connection and reload."; };
  document.head.appendChild(s);
}

start();
