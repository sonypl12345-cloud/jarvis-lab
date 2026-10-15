// GENESIS Neural Mesh LAB v0.3 — bounded authenticated HTTPS inference node.
// Reuses frozen v0.1 expert_0 weights / validated v0.2 packed SHA256.
// No database, files, secrets, account, Android, remote fetch, or side effects.
const SCHEMA = "GENESIS_NEURAL_MESH_HTTPS_NODE/0.3";
const PARENT = "f156378799b6a67ae8e6c754f00e302785fcc130fa914d4c830747655aaa7e00";
const PACKED_SHA = "674a35040841dc2b7bb7e227327a78ffa4a3c9a03fd16d0fd24cebb5eadf1577";
const B64 = "DlMOwKDMiz17rA+9bwFKP2f1WL4D42s9/DQHQGLqiL0eCts+MZmrvb/+gD/por29OJslQLV0ir1t4Pm/ereQPcAzCsBEwYo9Kg5EPxrn3b18lRQ/hpqKPygwAsCne5E9iVZavMSSgT8gQVs/Kp4jPDVh/b6aNPO8BE6oPOBIvrtqkky88QmeveohSj+RgNm7IGfCv2lnDL1NE4i+rdXRP+lJkD5PyCg/bBfKP4or8b/JgsW/SVvlPohKpj/RoD3ADG8ZPg==";
const binary = Uint8Array.from(atob(B64), c => c.charCodeAt(0));
if (binary.length !== 196) throw Error("WEIGHT_SIZE");
const dv = new DataView(binary.buffer, binary.byteOffset, binary.byteLength);
const weights = Array.from({length: 49}, (_,i) => dv.getFloat32(i*4, true));
const encoder = new TextEncoder();
const hex = (arr: Uint8Array) => Array.from(arr, b=>b.toString(16).padStart(2,"0")).join("");
async function sha(data: Uint8Array) { return hex(new Uint8Array(await crypto.subtle.digest("SHA-256", data))); }
const weightsReady = sha(binary).then(got => { if (got !== PACKED_SHA) throw Error("WEIGHTS_HASH_MISMATCH"); return true; });
function infer(x: number, y: number) {
  let z = weights[48];
  for (let i=0; i<12; i++) {
    const h = Math.tanh(weights[2*i]*x + weights[2*i+1]*y + weights[24+i]);
    z += weights[36+i]*h;
  }
  return z >= 0 ? 1 : 0;
}
const validInput = (p: unknown): p is [number,number] =>
  Array.isArray(p) && p.length===2 && p.every(v => typeof v==="number" && Number.isFinite(v) && Math.abs(v)<=2);
async function fixedCases():Promise<[number,number][]> {
  const result:[number,number][]=[];
  for (let i=0;i<256;i++) {
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode("genesis-neural-mesh-v02-case-"+i)));
    const v = new DataView(digest.buffer,digest.byteOffset,digest.byteLength);
    result.push([v.getUint16(0,true)*4/65535-2, v.getUint16(2,true)*4/65535-2]);
  }
  return result;
}
function reply(data:unknown,status=200) {
  return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
}
Deno.serve(async (req:Request) => {
  try {
    await weightsReady;
    if (req.method === "GET") return reply({schema:SCHEMA,ready:true,kind:"authenticated-bounded-lab",inference:"float32-weights-fp64-eval",max_input_pairs:16,weight_sha256:PACKED_SHA});
    if (req.method !== "POST") return reply({error:"METHOD_NOT_ALLOWED"},405);
    const ctype = req.headers.get("content-type")||"";
    if (!ctype.startsWith("application/json")) return reply({error:"JSON_REQUIRED"},415);
    const sz = Number(req.headers.get("content-length")||"0");
    if (!Number.isFinite(sz) || sz > 2048) return reply({error:"PAYLOAD_TOO_LARGE"},413);
    const body=await req.text();
    if (body.length>2048) return reply({error:"PAYLOAD_TOO_LARGE"},413);
    let arg:{operation?:unknown; inputs?:unknown};
    try {arg=JSON.parse(body);} catch {return reply({error:"BAD_JSON"},400);}
    if (!arg || typeof arg!=="object" || Array.isArray(arg)) return reply({error:"BAD_REQUEST"},400);
    let inputs:[number,number][];
    if (arg.operation==="selftest") {
      if (arg.inputs!==undefined) return reply({error:"NO_INPUTS_FOR_SELFTEST"},400);
      inputs=await fixedCases();
    } else if (arg.operation==="infer") {
      if (!Array.isArray(arg.inputs) || arg.inputs.length<1 || arg.inputs.length>16 || !arg.inputs.every(validInput))
        return reply({error:"INVALID_INPUTS_OR_LIMIT"},400);
      inputs=arg.inputs as [number,number][];
    } else return reply({error:"UNSUPPORTED_OPERATION"},400);
    const started=performance.now();
    const predictions=Uint8Array.from(inputs.map(([x,y])=>infer(x,y)));
    const prediction_sha256=await sha(predictions);
    return reply({schema:SCHEMA,operation:arg.operation,verified_weights:true,model_sha256:PARENT,packed_sha256:PACKED_SHA,cases:inputs.length,positive_count:predictions.reduce((s,v)=>s+v,0),predictions_sha256:prediction_sha256,predictions: arg.operation==="infer" ? Array.from(predictions) : undefined,compute_ms:Math.round((performance.now()-started)*1000)/1000});
  } catch (e) {console.error("NEURAL_MESH_V03_INTERNAL",String(e));return reply({error:"INTERNAL"},500);}
});
