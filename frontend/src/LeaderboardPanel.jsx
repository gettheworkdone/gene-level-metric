import React, { useEffect, useMemo, useState } from "react";
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
  Typography,
} from "@mui/material";
import {
  BarChart,
  Bar,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = {
  geneA: "#FFC000",
  geneB: "#FF5722",
  geneC: "#1088FF",
  complete: "#5CB8EA",
  fragmented: "#FFD700",
  missing: "#FF4C4C",
};

function medal(index) {
  if (index === 0) return "🥇";
  if (index === 1) return "🥈";
  if (index === 2) return "🥉";
  return "";
}

function rowStyle(index) {
  if (index === 0) return { backgroundColor: "#fff7cc" };
  if (index === 1) return { backgroundColor: "#f2f2f2" };
  if (index === 2) return { backgroundColor: "#f7e1c6" };
  return {};
}

function BuscoBar({ row }) {
  const total = Math.max((row.complete || 0) + (row.fragmented || 0) + (row.missing || 0), 1);
  const completePct = ((row.complete || 0) / total) * 100;
  const fragPct = ((row.fragmented || 0) / total) * 100;
  const missPct = ((row.missing || 0) / total) * 100;
  return (
    <Box sx={{ display: "flex", width: 240, height: 12, borderRadius: 1, overflow: "hidden", border: "1px solid #d0d7de" }}>
      <Box sx={{ width: `${completePct}%`, backgroundColor: COLORS.complete }} />
      <Box sx={{ width: `${fragPct}%`, backgroundColor: COLORS.fragmented }} />
      <Box sx={{ width: `${missPct}%`, backgroundColor: COLORS.missing }} />
    </Box>
  );
}

export default function LeaderboardPanel() {
  const [state, setState] = useState(null);
  const [modelName, setModelName] = useState("");
  const [predFile, setPredFile] = useState(null);
  const [submitMessage, setSubmitMessage] = useState("");

  const loadStatus = async () => {
    const response = await fetch("/api/leaderboard/status");
    const payload = await response.json();
    setState(payload);
  };

  useEffect(() => {
    loadStatus();
    const id = setInterval(loadStatus, 2000);
    return () => clearInterval(id);
  }, []);

  const launchDateText = useMemo(() => {
    if (!state?.launch_date) return "—";
    return new Date(state.launch_date * 1000).toLocaleString();
  }, [state]);

  const progress = useMemo(() => {
    if (!state || !state.total_models) return 0;
    return Math.round((state.completed_models / state.total_models) * 100);
  }, [state]);

  const mergedGeneRows = useMemo(() => {
    const rows = [...(state?.gene_rows || []), ...(state?.user_gene_rows || [])];
    return rows.sort((a, b) => (b.total_score || 0) - (a.total_score || 0));
  }, [state]);

  const mergedBuscoRows = useMemo(() => {
    const rows = [...(state?.busco_rows || []), ...(state?.user_busco_rows || [])];
    return rows.sort((a, b) => ((b.complete || 0) + (b.fragmented || 0)) - ((a.complete || 0) + (a.fragmented || 0)));
  }, [state]);

  const geneMax = useMemo(() => ({
    lncrna_exon: Math.max(0, ...mergedGeneRows.map((r) => r.lncrna_exon || 0)),
    mrna_exon: Math.max(0, ...mergedGeneRows.map((r) => r.mrna_exon || 0)),
    mrna_cds: Math.max(0, ...mergedGeneRows.map((r) => r.mrna_cds || 0)),
    total_score: Math.max(0, ...mergedGeneRows.map((r) => r.total_score || 0)),
  }), [mergedGeneRows]);

  const displayName = (modelId) => state?.model_name_map?.[modelId] || modelId;

  const geneChartData = useMemo(() => mergedGeneRows.map((row) => ({
    name: displayName(row.model_id),
    lncrna_exon: row.lncrna_exon,
    mrna_exon: row.mrna_exon,
    mrna_cds: row.mrna_cds,
  })), [mergedGeneRows, state]);

  const buscoChartData = useMemo(() => mergedBuscoRows.map((row) => ({
    name: displayName(row.model_id),
    complete: row.complete,
    fragmented: row.fragmented,
    missing: row.missing,
  })), [mergedBuscoRows, state]);

  const submitPrediction = async () => {
    if (!predFile) return;
    const pred_gff_text = await predFile.text();
    const response = await fetch("/api/leaderboard/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_name: modelName, pred_gff_text }),
    });
    const payload = await response.json();
    if (!response.ok) {
      setSubmitMessage(payload.detail || "Submission failed");
      return;
    }
    setSubmitMessage(`Submitted. Current queue position: ${payload.position}.`);
    setModelName("");
    setPredFile(null);
  };

  return (
    <Stack spacing={2.2}>
      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Stack spacing={1.2}>
          <Typography variant="h5">Gene segmentation benchmark leaderboard</Typography>
          <Typography color="text.secondary">
            This benchmark evaluates gene segmentation prediction quality across multiple models using the gene-level metric and the BUSCO tool.
            Gene-level scoring follows the \"metric usage and description section\" of this space, while BUSCO is computed with version 5.7.1
            using the mammalia_odb10 lineage that you can load from the repository connected to this space.
          </Typography>
          <Typography color="text.secondary">
            You may submit model predictions to the permanent benchmark by opening a pull request with a compliant .gff file in
            <a href="https://github.com/alexeyshmelev/genatator-leaderboard-predictions" target="_blank" rel="noreferrer">this repository</a>.
            You can also evaluate your model immediately through the upload panel below. Because this is a gene segmentation benchmark, the .gff
            structure must strictly follow repository instructions to ensure correct assessment.
          </Typography>
        </Stack>
      </Paper>

      {state?.running ? (
        <Paper className="glass-card" sx={{ p: 2.4 }}>
          <Stack spacing={1.5}>
            <Typography variant="h6">Building leaderboard...</Typography>
            <Typography sx={{ alignSelf: "flex-start" }}>
              {state?.stage || "Building leaderboard"}
              {state?.current_model ? ` • Current model: ${displayName(state.current_model)}` : ""}
            </Typography>
            <LinearProgress variant="determinate" value={progress} />
            <Typography variant="body2" color="text.secondary">
              {state?.completed_models || 0}/{state?.total_models || 0} completed • {progress}%
            </Typography>
            {state?.message ? <Alert severity="info">{state.message}</Alert> : null}
            {state?.error ? <Alert severity="error">{state.error}</Alert> : null}
          </Stack>
        </Paper>
      ) : null}

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Gene-level metric distribution</Typography>
        <Box sx={{ width: "100%", height: 340 }}>
          <ResponsiveContainer>
            <BarChart layout="vertical" data={geneChartData} margin={{ top: 10, right: 10, bottom: 10, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={230} />
              <Tooltip />
              <Legend />
              <Bar dataKey="mrna_cds" stackId="gene" fill={COLORS.geneC} name="CDS mRNA" />
              <Bar dataKey="mrna_exon" stackId="gene" fill={COLORS.geneB} name="exon mRNA" />
              <Bar dataKey="lncrna_exon" stackId="gene" fill={COLORS.geneA} name="exon lncRNA" />
            </BarChart>
          </ResponsiveContainer>
        </Box>
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Gene-level leaderboard</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell><TableCell>Model</TableCell><TableCell>exon lncRNA</TableCell><TableCell>exon mRNA</TableCell><TableCell>CDS mRNA</TableCell><TableCell>Total score</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {mergedGeneRows.map((row, idx) => (
              <TableRow key={row.model_id} sx={rowStyle(idx)}>
                <TableCell>{idx + 1}</TableCell>
                <TableCell>{displayName(row.model_id)} {medal(idx)}</TableCell>
                <TableCell sx={{ fontWeight: row.lncrna_exon === geneMax.lncrna_exon ? 700 : 400 }}>{row.lncrna_exon}</TableCell>
                <TableCell sx={{ fontWeight: row.mrna_exon === geneMax.mrna_exon ? 700 : 400 }}>{row.mrna_exon}</TableCell>
                <TableCell sx={{ fontWeight: row.mrna_cds === geneMax.mrna_cds ? 700 : 400 }}>{row.mrna_cds}</TableCell>
                <TableCell sx={{ fontWeight: row.total_score === geneMax.total_score ? 700 : 400 }}>{row.total_score}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>BUSCO metric distribution</Typography>
        <Box sx={{ width: "100%", height: 340 }}>
          <ResponsiveContainer>
            <BarChart layout="vertical" data={buscoChartData} margin={{ top: 10, right: 10, bottom: 10, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={230} />
              <Tooltip />
              <Legend />
              <Bar dataKey="complete" stackId="busco" fill={COLORS.complete} name="Complete" />
              <Bar dataKey="fragmented" stackId="busco" fill={COLORS.fragmented} name="Fragmented" />
              <Bar dataKey="missing" stackId="busco" fill={COLORS.missing} name="Missing" />
            </BarChart>
          </ResponsiveContainer>
        </Box>
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>BUSCO leaderboard</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell><TableCell>Model</TableCell><TableCell>Complete</TableCell><TableCell>Fragmented</TableCell><TableCell>Missing</TableCell><TableCell>Distribution</TableCell><TableCell>Colored GFF</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {mergedBuscoRows.map((row, idx) => (
              <TableRow key={row.model_id} sx={rowStyle(idx)}>
                <TableCell>{idx + 1}</TableCell>
                <TableCell>{displayName(row.model_id)} {medal(idx)}</TableCell>
                <TableCell>{row.complete}</TableCell>
                <TableCell>{row.fragmented}</TableCell>
                <TableCell>{row.missing}</TableCell>
                <TableCell><BuscoBar row={row} /></TableCell>
                <TableCell>{row.colored_gff_url ? <Button size="small" component="a" href={row.colored_gff_url}>Download colored GFF</Button> : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6">Evaluate your own model</Typography>
        <Typography color="text.secondary" sx={{ mb: 1.2 }}>
          Uploaded predictions are assessed against the current benchmark and appear temporarily in the tables and charts.
          These temporary entries are not stored permanently and disappear after page refresh.
        </Typography>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.2}>
          <TextField label="Model name" value={modelName} onChange={(e) => setModelName(e.target.value)} sx={{ width: { xs: "100%", md: "35%" } }} />
          <Button component="label" variant="outlined">Upload .gff<input hidden type="file" accept=".gff,.gff3,.txt" onChange={(e) => setPredFile(e.target.files?.[0] || null)} /></Button>
          <Button variant="contained" onClick={submitPrediction} disabled={!predFile}>Submit</Button>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Queue length: {state?.queue_length || 0}. Current workload: {state?.queue_current || "idle"}.
        </Typography>
        {submitMessage ? <Alert severity="info" sx={{ mt: 1 }}>{submitMessage}</Alert> : null}
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="body2" color="text.secondary">Benchmark launch date: {launchDateText}</Typography>
      </Paper>
    </Stack>
  );
}
