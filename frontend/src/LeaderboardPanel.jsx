import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip as MuiTooltip,
  Typography,
} from "@mui/material";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = { geneA: "#FFC000", geneB: "#FF5722", geneC: "#1088FF", complete: "#5CB8EA", fragmented: "#FFD700", missing: "#FF4C4C" };
const LEADERBOARD_SECTIONS = [["tldr", "TLDR"], ["gene-level-leaderboard", "Gene-level leaderboard"], ["busco-leaderboard", "BUSCO leaderboard"], ["gene-level-metric-distribution", "Gene-level metric distribution"], ["busco-metric-distribution", "BUSCO metric distribution"], ["leaderboard-description", "Leaderboard description"], ["evaluate-your-own-model", "Evaluate your own model"]];

function PanelTitle({ children, sx = {} }) { return <Typography variant="h5" sx={{ mb: 1, ...sx }}>{children}</Typography>; }
function HeaderTooltip({ label, description }) { return <MuiTooltip arrow placement="top" enterDelay={250} title={<Typography variant="body2" sx={{ lineHeight: 1.45 }}>{description}</Typography>}><Box component="span" className="metric-header-help">{label}</Box></MuiTooltip>; }
const medal = (i) => (i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : "");
const rowStyle = (i) => (i === 0 ? { backgroundColor: "#fff7cc" } : i === 1 ? { backgroundColor: "#f2f2f2" } : i === 2 ? { backgroundColor: "#f7e1c6" } : {});

function BuscoBar({ row }) { const total = Math.max((row.complete || 0) + (row.fragmented || 0) + (row.missing || 0), 1); return <Box sx={{ display: "flex", width: 240, height: 12, borderRadius: 1, overflow: "hidden", border: "1px solid #d0d7de" }}><Box sx={{ width: `${((row.complete || 0) / total) * 100}%`, backgroundColor: COLORS.complete }} /><Box sx={{ width: `${((row.fragmented || 0) / total) * 100}%`, backgroundColor: COLORS.fragmented }} /><Box sx={{ width: `${((row.missing || 0) / total) * 100}%`, backgroundColor: COLORS.missing }} /></Box>; }

export default function LeaderboardPanel() {
  const [state, setState] = useState(null);
  const [modelName, setModelName] = useState("");
  const [predFile, setPredFile] = useState(null);
  const [temporaryGeneRows, setTemporaryGeneRows] = useState([]);
  const [temporaryBuscoRows, setTemporaryBuscoRows] = useState([]);
  const [temporaryNameMap, setTemporaryNameMap] = useState({});
  const [temporaryDownloadUrls, setTemporaryDownloadUrls] = useState({});
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const predFileInputRef = useRef(null);

  useEffect(() => () => Object.values(temporaryDownloadUrls).forEach((u) => URL.revokeObjectURL(u)), [temporaryDownloadUrls]);
  const loadStatus = async () => setState(await (await fetch("/api/leaderboard/status")).json());
  useEffect(() => { loadStatus(); const id = setInterval(loadStatus, 2000); return () => clearInterval(id); }, []);

  const launchDateText = useMemo(() => (!state?.launch_date ? "—" : new Date(state.launch_date * 1000).toLocaleString()), [state]);
  const progress = useMemo(() => (!state || !state.total_models ? 0 : Math.round((state.completed_models / state.total_models) * 100)), [state]);
  const mergedGeneRows = useMemo(() => [...(state?.gene_rows || []), ...temporaryGeneRows].sort((a, b) => (b.total_score || 0) - (a.total_score || 0)), [state, temporaryGeneRows]);
  const mergedBuscoRows = useMemo(() => [...(state?.busco_rows || []), ...temporaryBuscoRows].sort((a, b) => ((b.complete || 0) + (b.fragmented || 0)) - ((a.complete || 0) + (a.fragmented || 0))), [state, temporaryBuscoRows]);
  const geneMax = useMemo(() => ({ lncrna_exon: Math.max(0, ...mergedGeneRows.map((r) => r.lncrna_exon || 0)), mrna_exon: Math.max(0, ...mergedGeneRows.map((r) => r.mrna_exon || 0)), mrna_cds: Math.max(0, ...mergedGeneRows.map((r) => r.mrna_cds || 0)), total_score: Math.max(0, ...mergedGeneRows.map((r) => r.total_score || 0)) }), [mergedGeneRows]);
  const displayName = (id) => temporaryNameMap[id] || state?.model_name_map?.[id] || id;
  const geneChartData = useMemo(() => mergedGeneRows.map((r) => ({ name: displayName(r.model_id), lncrna_exon: r.lncrna_exon, mrna_exon: r.mrna_exon, mrna_cds: r.mrna_cds })), [mergedGeneRows, state, temporaryNameMap]);
  const buscoChartData = useMemo(() => mergedBuscoRows.map((r) => ({ name: displayName(r.model_id), complete: r.complete, fragmented: r.fragmented, missing: r.missing })), [mergedBuscoRows, state, temporaryNameMap]);

  const submitPrediction = async () => {
    if (!predFile || uploadLoading) return;
    setUploadLoading(true); setUploadMessage(""); setUploadError("");
    try {
      const pred_gff_text = await predFile.text();
      const submitRes = await fetch("/api/leaderboard/submit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model_name: modelName, pred_gff_text }) });
      const submitPayload = await submitRes.json();
      if (!submitRes.ok) throw new Error(submitPayload.detail || "Submission failed");
      const { submission_id } = submitPayload;
      const poll = async () => {
        const r = await fetch(`/api/leaderboard/submission/${submission_id}`); const p = await r.json();
        if (p.status === "completed") {
          const { model_id, model_name, gene_row, busco_row } = p;
          setTemporaryGeneRows((rows) => [...rows.filter((x) => x.model_id !== model_id), gene_row]);
          setTemporaryNameMap((m) => ({ ...m, [model_id]: model_name }));
          let finalBusco = { ...busco_row };
          if (busco_row?.colored_gff_text) {
            const blobUrl = URL.createObjectURL(new Blob([busco_row.colored_gff_text], { type: "text/plain" }));
            setTemporaryDownloadUrls((prev) => { if (prev[model_id]) URL.revokeObjectURL(prev[model_id]); return { ...prev, [model_id]: blobUrl }; });
            finalBusco = { ...finalBusco, colored_gff_url: blobUrl }; delete finalBusco.colored_gff_text;
          }
          setTemporaryBuscoRows((rows) => [...rows.filter((x) => x.model_id !== model_id), finalBusco]);
          setUploadLoading(false); setUploadMessage("Finished. This temporary result is shown only in this browser session and will disappear after refresh.");
          setModelName(""); setPredFile(null); if (predFileInputRef.current) predFileInputRef.current.value = ""; return;
        }
        if (p.status === "failed") { setUploadLoading(false); setUploadError(p.error || "Submission failed"); return; }
        if (p.status === "expired") { setUploadLoading(false); setUploadError("Temporary submission result expired before it could be retrieved. Please submit again."); return; }
        window.setTimeout(poll, 2000);
      };
      window.setTimeout(poll, 2000);
    } catch (e) { setUploadLoading(false); setUploadError(e.message || "Submission failed"); }
  };

  return <Stack spacing={2.2}>
    <Paper sx={{ px: { xs: 4.4, md: 5.2 }, pt: { xs: 0.4, md: 0.5 }, pb: { xs: 0.4, md: 0.5 }, order: -1, mt: -1.1, mb: 2.0, position: "sticky", top: 74, zIndex: 20, backgroundColor: "transparent !important", boxShadow: "none", backdropFilter: "none", border: "none" }}><Stack direction="row" spacing={1} sx={{ overflowX: "auto", overflowY: "visible", whiteSpace: "nowrap", justifyContent: "center", pt: 1.0, pb: 1.0, px: 1.2 }}>{LEADERBOARD_SECTIONS.map(([id, label]) => <Button key={id} size="small" href={`#${id}`} variant="contained" sx={{ backgroundColor: "#d9f4ec", color: "primary.main", borderRadius: "999px", textTransform: "none", boxShadow: "0 1px 2px rgba(15, 23, 42, 0.12)", my: 0.6, px: 1.6, "&:hover": { backgroundColor: "#c7ecdf" } }}>{label}</Button>)}</Stack></Paper>
    {state?.running ? <Paper className="glass-card" sx={{ p: 2.4 }}><Stack spacing={1.5}><PanelTitle>Building leaderboard</PanelTitle><Typography sx={{ alignSelf: "flex-start" }}>{state?.stage || "Building leaderboard"}{state?.current_model ? ` • Current model: ${displayName(state.current_model)}` : ""}</Typography><LinearProgress variant="determinate" value={progress} /><Typography variant="body2" color="text.secondary">{state?.completed_models || 0}/{state?.total_models || 0} completed • {progress}%</Typography>{state?.error ? <Alert severity="error">{state.error}</Alert> : null}</Stack></Paper> : null}
    <Paper className="glass-card" id="tldr" sx={{ p: { xs: 2.2, md: 3 }, scrollMarginTop: "132px" }}><Stack spacing={1.4}><PanelTitle>TLDR</PanelTitle><Typography color="text.secondary" sx={{ fontSize: "0.92rem", lineHeight: 1.55, fontWeight: 700 }}>This benchmark compares gene-segmentation models on transcript-coordinate prediction files for T2T human chromosome 20. Higher gene-level scores mean more transcripts with exactly correct exon/CDS segmentation. BUSCO reports complete, fragmented, and missing mammalian single-copy orthologs. Tested models are expected to receive only the DNA sequence of an individual transcript, without intergenic regions or neighboring-gene context. Temporary uploads are shown only in the current browser session and disappear after page refresh. Permanent entries must be submitted by pull request.</Typography></Stack></Paper>
    <Paper className="glass-card" id="gene-level-leaderboard" sx={{ p: 2.4, scrollMarginTop: "132px" }}><PanelTitle>Gene-level leaderboard</PanelTitle><Table size="small"><TableHead><TableRow><TableCell>Rank</TableCell><TableCell>Model</TableCell><TableCell><HeaderTooltip label="exon lncRNA" description="Number of lnc_RNA transcripts whose exon segmentation is exactly matched by the model." /></TableCell><TableCell><HeaderTooltip label="exon mRNA" description="Number of mRNA transcripts whose exon segmentation is exactly matched by the model." /></TableCell><TableCell><HeaderTooltip label="CDS mRNA" description="Number of mRNA transcripts whose CDS segmentation is exactly matched by the model." /></TableCell><TableCell><HeaderTooltip label="Total score" description="Sum of exon lncRNA, exon mRNA, and CDS mRNA exact-match counts. Higher is better." /></TableCell></TableRow></TableHead><TableBody>{mergedGeneRows.map((row, idx) => <TableRow key={row.model_id} sx={rowStyle(idx)}><TableCell>{idx + 1}</TableCell><TableCell>{displayName(row.model_id)} {medal(idx)}</TableCell><TableCell sx={{ fontWeight: row.lncrna_exon === geneMax.lncrna_exon ? 700 : 400 }}>{row.lncrna_exon}</TableCell><TableCell sx={{ fontWeight: row.mrna_exon === geneMax.mrna_exon ? 700 : 400 }}>{row.mrna_exon}</TableCell><TableCell sx={{ fontWeight: row.mrna_cds === geneMax.mrna_cds ? 700 : 400 }}>{row.mrna_cds}</TableCell><TableCell sx={{ fontWeight: row.total_score === geneMax.total_score ? 700 : 400 }}>{row.total_score}</TableCell></TableRow>)}</TableBody></Table></Paper>
    <Paper className="glass-card" id="busco-leaderboard" sx={{ p: 2.4, scrollMarginTop: "132px" }}><PanelTitle>BUSCO leaderboard</PanelTitle><Table size="small"><TableHead><TableRow><TableCell>Rank</TableCell><TableCell>Model</TableCell><TableCell><HeaderTooltip label="Complete" description="Number of BUSCO genes found as complete in the model prediction." /></TableCell><TableCell><HeaderTooltip label="Fragmented" description="Number of BUSCO genes found only as fragmented in the model prediction." /></TableCell><TableCell><HeaderTooltip label="Missing" description="Number of BUSCO genes not found by BUSCO in the model prediction." /></TableCell><TableCell><HeaderTooltip label="Distribution" description="Visual summary of Complete, Fragmented, and Missing BUSCO counts for this model." /></TableCell><TableCell><HeaderTooltip label="Colored GFF" description="Download a BUSCO-colored GFF for visual inspection. Transcript records are colored by BUSCO status." /></TableCell></TableRow></TableHead><TableBody>{mergedBuscoRows.map((row, idx) => <TableRow key={row.model_id} sx={rowStyle(idx)}><TableCell>{idx + 1}</TableCell><TableCell>{displayName(row.model_id)} {medal(idx)}</TableCell><TableCell>{row.complete}</TableCell><TableCell>{row.fragmented}</TableCell><TableCell>{row.missing}</TableCell><TableCell><BuscoBar row={row} /></TableCell><TableCell>{row.colored_gff_url ? <Button size="small" component="a" href={row.colored_gff_url}>Download</Button> : "—"}</TableCell></TableRow>)}</TableBody></Table></Paper>
    <Paper className="glass-card" id="gene-level-metric-distribution" sx={{ p: 2.4, scrollMarginTop: "132px" }}><PanelTitle>Gene-level metric distribution</PanelTitle><Box sx={{ width: "100%", height: 510 }}><ResponsiveContainer><BarChart layout="vertical" data={geneChartData} margin={{ top: 10, right: 10, bottom: 10, left: 20 }}><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" domain={[0, state?.gene_axis_max || 100]} /><YAxis type="category" dataKey="name" width={230} /><RechartsTooltip /><Legend /><Bar dataKey="mrna_cds" stackId="gene" fill={COLORS.geneC} name="CDS mRNA" /><Bar dataKey="mrna_exon" stackId="gene" fill={COLORS.geneB} name="exon mRNA" /><Bar dataKey="lncrna_exon" stackId="gene" fill={COLORS.geneA} name="exon lncRNA" /></BarChart></ResponsiveContainer></Box></Paper>
    <Paper className="glass-card" id="busco-metric-distribution" sx={{ p: 2.4, scrollMarginTop: "132px" }}><PanelTitle>BUSCO metric distribution</PanelTitle><Box sx={{ width: "100%", height: 510 }}><ResponsiveContainer><BarChart layout="vertical" data={buscoChartData} margin={{ top: 10, right: 10, bottom: 10, left: 20 }}><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" domain={[0, state?.busco_axis_max || 275]} /><YAxis type="category" dataKey="name" width={230} /><RechartsTooltip /><Legend /><Bar dataKey="complete" stackId="busco" fill={COLORS.complete} name="Complete" /><Bar dataKey="fragmented" stackId="busco" fill={COLORS.fragmented} name="Fragmented" /><Bar dataKey="missing" stackId="busco" fill={COLORS.missing} name="Missing" /></BarChart></ResponsiveContainer></Box></Paper>
    <Paper className="glass-card" id="leaderboard-description" sx={{ p: 2.4, scrollMarginTop: "132px" }}><Stack spacing={1.2}><PanelTitle>Leaderboard description</PanelTitle><Typography color="text.secondary">This benchmark evaluates gene segmentation prediction quality across multiple models using the gene-level metric and the BUSCO tool.</Typography><Typography color="text.secondary">Gene-level scoring follows the Metrics description section of this Space, while BUSCO is computed with version 5.7.1 using the locally provided mammalia_odb10 lineage directory.</Typography><Typography color="text.secondary">This benchmark is defined on the T2T human genome assembly (GCF_009914755.1) and evaluates all 3998 mRNA and lncRNA transcripts from chromosome 20 (NC_060944.1) across all 980 genes in scope.</Typography><Typography color="text.secondary" sx={{ fontWeight: 700 }}>Important input assumption: each tested model is expected to receive only the DNA sequence of an individual transcript as input. The model input must not include intergenic regions, neighboring genes, or other genomic context. Accordingly, submitted prediction GFF files are transcript-coordinate annotations: the seqid column should identify the transcript being annotated, not a chromosome interval containing intergenic sequence.</Typography><Typography color="text.secondary">For BUSCO results, we provide a download option that returns model predictions colored at transcript level as complete, fragmented, or not found. This output is ready for visualization in IGV genome browser and supports visual inspection of predicted structures.</Typography><Typography color="text.secondary">You may submit model predictions to the permanent benchmark by opening a pull request with a compliant .gff file in <a href="https://github.com/alexeyshmelev/genatator-leaderboard-predictions" target="_blank" rel="noreferrer">this repository</a>. You can also evaluate your model immediately through the upload panel below.</Typography><Typography variant="body2" color="text.secondary">Benchmark launch date: {launchDateText}</Typography></Stack></Paper>
    <Paper className="glass-card" id="evaluate-your-own-model" sx={{ p: 2.4, scrollMarginTop: "132px" }}><PanelTitle>Evaluate your own model</PanelTitle><Typography color="text.secondary" sx={{ mb: 1.2 }}>Uploaded predictions are assessed against the current benchmark and appear temporarily in the tables and charts. These temporary entries are not stored permanently and disappear after page refresh.</Typography><Stack direction={{ xs: "column", md: "row" }} spacing={1.2} alignItems="center"><TextField label="Model name" value={modelName} onChange={(e) => setModelName(e.target.value)} sx={{ width: { xs: "100%", md: "35%" } }} /><Button component="label" variant="outlined" sx={{ height: 56 }}>Upload .gff<input ref={predFileInputRef} hidden type="file" accept=".gff,.gff3,.txt" onChange={(e) => setPredFile(e.target.files?.[0] || null)} /></Button><Button variant="contained" onClick={submitPrediction} disabled={!predFile || uploadLoading} sx={{ height: 56 }}>Submit</Button></Stack><Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Queue length: {state?.queue_length || 0}.</Typography>{uploadLoading ? <Box className="score-calc-animation"><span className="orb" /><Typography color="text.secondary">Queued / calculating gene-level and BUSCO metrics for your model...</Typography></Box> : null}{uploadMessage ? <Alert severity="success" sx={{ mt: 1 }}>{uploadMessage}</Alert> : null}{uploadError ? <Alert severity="error" sx={{ mt: 1 }}>{uploadError}</Alert> : null}</Paper>
  </Stack>;
}
