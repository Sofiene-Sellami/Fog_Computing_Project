import React, { useState, useEffect } from "react";

export default function App() {
  const [frame, setFrame] = useState(null);
  const [result, setResult] = useState("Aucun résultat de détection...");
  const [nodes, setNodes] = useState([]);

    const MASTER_URL = "http://KS:8000";
  // 🔹 Fetch annotated frame
  useEffect(() => {
    const interval = setInterval(async () => {
      console.log("📡 Requesting /last_frame ...");

      try {
        const res = await fetch(`${MASTER_URL}/last_frame`);
        const data = await res.json();

        console.log("✅ /last_frame response:", data);

        if (data.image) {
          setFrame(`data:image/jpeg;base64,${data.image}`);
        } else {
          console.log("⚠️ /last_frame returned no image");
        }
      } catch (err) {
        console.error("❌ Erreur fetch last_frame:", err);
      }
    }, 10);

    return () => clearInterval(interval);
  }, []);

  // 🔹 Fetch last YOLO result
  useEffect(() => {
    const interval = setInterval(async () => {
      console.log("📡 Requesting /last_result ...");

      try {
        const res = await fetch(`${MASTER_URL}/last_result`);
        const data = await res.json();

        console.log("✅ /last_result response:", data);

        if (!data.message) setResult(data);
        else console.log("⚠️ No result returned yet");
      } catch (err) {
        console.error("❌ Erreur fetch last_result:", err);
      }
    }, 10);

    return () => clearInterval(interval);
  }, []);

  // 🔹 Fetch nodes
  useEffect(() => {
    const interval = setInterval(async () => {
      console.log("📡 Requesting /nodes ...");

      try {
        const res = await fetch(`${MASTER_URL}/nodes`);
        const data = await res.json();

        console.log("✅ /nodes response:", data);

        setNodes(data || []);
      } catch (err) {
        console.error("❌ Erreur fetch nodes:", err);
      }
    }, 10);

    return () => clearInterval(interval);
  }, []);

  const getColor = (status) => {
    if (status === 1) return "#4ade80"; // green
    if (status === 0) return "#f87171"; // red busy
    return "#60a5fa"; // blue unreachable
  };

  return (
    <div style={styles.container}>
      <div style={styles.left}>
        <div style={styles.imageBox}>
          {frame ? (
            <img src={frame} style={styles.image} alt="Video" />
          ) : (
            <p>Pas encore d'image</p>
          )}
        </div>

        <div style={styles.resultBox}>
          {typeof result === "string" ? (
            result
          ) : !result.detections || result.detections.length === 0 ? (
            <div>Aucune détection</div>
          ) : (
            result.detections.map((det, i) => (
              <div key={i}>
                {det.class} ({(det.confidence * 100).toFixed(1)}%) at [
                {det.bbox.map((n) => n.toFixed(1)).join(", ")}]
              </div>
            ))
          )}
        </div>
      </div>

      <div style={styles.right}>
        <div style={styles.header}>Nodes Status</div>
        {["FogNode1", "FogNode2", "FogNode3"].map((name) => {
          const node = nodes.find((n) => n.name === name);
          return (
            <div
              key={name}
              style={{
                ...styles.nodeStyle,
                backgroundColor: getColor(node?.available),
              }}
            >
              {name}{" "}
              {node?.available === 1
                ? "🟢"
                : node?.available === 0
                ? "🔴"
                : "🔵"}
            </div>
          );
        })}
      </div>
    </div>
  );
}
const styles = {
  container: { display: "flex", width: "100vw", height: "100vh", justifyContent: "center", alignItems: "center", background: "linear-gradient(135deg,#fbc2eb,#fde047)" },
  left: { display: "flex", flexDirection: "column", marginRight: "200px", gap: "20px", alignItems: "center" },
  right: { display: "flex", flexDirection: "column", alignItems: "center", gap: "15px" },
  header: { width: "220px", padding: "12px", textAlign: "center", fontWeight: "bold", fontSize: "20px", borderRadius: "10px", background: "#9f23d1", color: "white" },
  imageBox: { width: "420px", height: "320px", borderRadius: "15px", background: "#d8b4fe", display: "flex", justifyContent: "center", alignItems: "center", border: "3px dashed white", overflow: "hidden" },
  image: { width: "100%", height: "100%", objectFit: "cover", borderRadius: "15px" },
  resultBox: { width: "420px", padding: "15px", borderRadius: "10px", background: "#c084fc", textAlign: "center", fontSize: "18px", fontWeight: "bold", color: "white", maxHeight: "220px", overflowY: "auto" },
  nodeStyle: { width: "200px", padding: "12px", borderRadius: "10px", fontWeight: "bold", color: "white", textAlign: "center", fontSize: "18px" },
};