// Tooltips for the Progress charts: hover, tap or drag across a chart, or focus it and use the arrow keys,
// to read the exact value of the nearest point or bar. Without this script, the browser's own hover titles still work.
document.querySelectorAll(".chart-plot").forEach((plot) => {
  const marks = [...plot.querySelectorAll("[data-tip]")];
  const tip = plot.querySelector(".chart-tip");
  if (!marks.length || !tip) return;

  // Our tooltip replaces the native ones, so they don't show twice.
  plot.querySelectorAll("title").forEach((title) => title.remove());
  marks.forEach((mark) => mark.removeAttribute("title"));

  let active = -1;

  function show(index) {
    marks[active]?.classList.remove("is-active");
    active = index;
    const mark = marks[index];
    const x = Number(mark.dataset.x);
    mark.classList.add("is-active");
    tip.textContent = mark.dataset.tip;
    tip.style.left = `${x}%`;
    tip.style.top = `${mark.dataset.y}%`;
    // Near the edges, anchor the tooltip to the side so it stays inside the card.
    tip.classList.toggle("start", x < 20);
    tip.classList.toggle("end", x > 80);
    tip.hidden = false;
  }

  function hide() {
    marks[active]?.classList.remove("is-active");
    tip.hidden = true;
  }

  function nearest(clientX) {
    const rect = plot.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * 100;
    let best = 0;
    marks.forEach((mark, i) => {
      if (Math.abs(mark.dataset.x - x) < Math.abs(marks[best].dataset.x - x)) best = i;
    });
    return best;
  }

  plot.addEventListener("pointermove", (event) => show(nearest(event.clientX)));
  plot.addEventListener("pointerdown", (event) => show(nearest(event.clientX)));
  plot.addEventListener("pointerleave", (event) => {
    if (event.pointerType === "mouse" && document.activeElement !== plot) hide();
  });
  plot.addEventListener("focus", () => show(active >= 0 ? active : marks.length - 1));
  plot.addEventListener("blur", hide);
  plot.addEventListener("keydown", (event) => {
    const moves = { ArrowLeft: active - 1, ArrowRight: active + 1, Home: 0, End: marks.length - 1 };
    if (event.key in moves) {
      event.preventDefault();
      show(Math.min(Math.max(moves[event.key], 0), marks.length - 1));
    } else if (event.key === "Escape") {
      hide();
    }
  });
});
