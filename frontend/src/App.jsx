import { useState } from "react";
import { EncodeForm, DecodeForm } from "./Pages.jsx";

export default function App() {
  const [page, setPage] = useState("encode");

  return (
    <div className="app">
      <div className="app-header">
        <h1>Video Steganography</h1>
        <p className="tagline">Hide encrypted messages inside video frames using DWT + DCT + SVD frequency-domain embedding</p>
      </div>
      <nav>
        <button onClick={() => setPage("encode")} className={page === "encode" ? "active" : ""}>
          Hide Message
        </button>
        <button onClick={() => setPage("decode")} className={page === "decode" ? "active" : ""}>
          Extract Message
        </button>
      </nav>
      {page === "encode" ? <EncodeForm /> : <DecodeForm />}
    </div>
  );
}
