export async function encode(video, message, password) {
  const form = new FormData();
  form.append("video", video);
  form.append("message", message);
  form.append("password", password);
  const res = await fetch("/encode", { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function decode(video, password) {
  const form = new FormData();
  form.append("video", video);
  form.append("password", password);
  const res = await fetch("/decode", { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
