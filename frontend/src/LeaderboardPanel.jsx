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
  Typography,
} from "@mui/material";

function BuscoBar({ row }) {
  const total = Math.max((row.complete || 0) + (row.fragmented || 0) + (row.missing || 0), 1);
  const completePct = ((row.complete || 0) / total) * 100;
  const fragPct = ((row.fragmented || 0) / total) * 100;
  const missPct = ((row.missing || 0) / total) * 100;

  return (
    <Box sx={{ display: "flex", width: 240, height: 12, borderRadius: 1, overflow: "hidden", border: "1px solid #d0d7de" }}>
      <Box sx={{ width: `${completePct}%`, backgroundColor: "#16a34a" }} />
      <Box sx={{ width: `${fragPct}%`, backgroundColor: "#f59e0b" }} />
      <Box sx={{ width: `${missPct}%`, backgroundColor: "#ef4444" }} />
    </Box>
  );
}

export default function LeaderboardPanel() {
  const [state, setState] = useState(null);

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

  const start = async () => {
    await fetch("/api/leaderboard/start", { method: "POST" });
    await loadStatus();
  };

  const progress = useMemo(() => {
    if (!state || !state.total_models) return 0;
    return Math.round((state.completed_models / state.total_models) * 100);
  }, [state]);

  return (
    <Stack spacing={2.2}>
      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Stack spacing={1.5}>
          <Typography variant="h5">Leaderboard (live pipeline)</Typography>
          <Typography color="text.secondary">
            Click start to clone predictions and compute gene-level + BUSCO metrics for every .gff file.
          </Typography>
          <Stack direction="row" spacing={1.2}>
            <Button variant="contained" onClick={start} disabled={state?.running}>Start / Rebuild leaderboard</Button>
            <Typography sx={{ alignSelf: "center" }}>
              {state?.stage ? `Stage: ${state.stage}` : "Stage: idle"}
              {state?.current_model ? ` • Current: ${state.current_model}` : ""}
            </Typography>
          </Stack>
          <LinearProgress variant="determinate" value={progress} />
          <Typography variant="body2" color="text.secondary">
            {state?.completed_models || 0}/{state?.total_models || 0} completed • {progress}%
          </Typography>
          {state?.message ? <Alert severity="info">{state.message}</Alert> : null}
          {state?.error ? <Alert severity="error">{state.error}</Alert> : null}
        </Stack>
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Gene-level leaderboard</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Model</TableCell><TableCell>exon lncRNA</TableCell><TableCell>exon mRNA</TableCell><TableCell>CDS mRNA</TableCell><TableCell>Gene score</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(state?.gene_rows || []).map((row) => (
              <TableRow key={row.model_id}>
                <TableCell>{row.model_id}</TableCell><TableCell>{row.lncrna_exon}</TableCell><TableCell>{row.mrna_exon}</TableCell><TableCell>{row.mrna_cds}</TableCell><TableCell>{row.score_gene}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>BUSCO leaderboard</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Model</TableCell><TableCell>Complete</TableCell><TableCell>Fragmented</TableCell><TableCell>Missing</TableCell><TableCell>Graph</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(state?.busco_rows || []).map((row) => (
              <TableRow key={row.model_id}>
                <TableCell>{row.model_id}</TableCell><TableCell>{row.complete}</TableCell><TableCell>{row.fragmented}</TableCell><TableCell>{row.missing}</TableCell><TableCell><BuscoBar row={row} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
