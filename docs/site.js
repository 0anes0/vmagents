const t = document.documentElement.lang === "tr"
  ? { copy: "Kopyala", done: "Kopyalandı", fail: "Seçip kopyala" }
  : { copy: "Copy", done: "Copied", fail: "Select and copy" };
for (const pre of document.querySelectorAll("pre")) {
  const b = document.createElement("button");
  b.className = "copy"; b.textContent = t.copy;
  b.onclick = async () => {
    const text = [...pre.childNodes].filter(n => n !== b && !(n.classList && n.classList.contains("c")))
      .map(n => n.textContent).join("").split("\n").map(l => l.trimEnd()).filter(Boolean).join("\n");
    try { await navigator.clipboard.writeText(text); b.textContent = t.done; }
    catch { b.textContent = t.fail; }
    setTimeout(() => (b.textContent = t.copy), 1500);
  };
  pre.appendChild(b);
}
