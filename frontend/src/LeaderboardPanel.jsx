import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
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


  const progress = useMemo(() => {
    if (!state || !state.total_models) return 0;
    return Math.round((state.completed_models / state.total_models) * 100);
  }, [state]);

  const geneChartData = useMemo(() => {
    return (state?.gene_rows || []).map((row) => ({
      name: row.model_id,
      lncrna_exon: row.lncrna_exon,
      mrna_exon: row.mrna_exon,
      mrna_cds: row.mrna_cds,
    }));
  }, [state]);

  const buscoChartData = useMemo(() => {
    return (state?.busco_rows || []).map((row) => ({
      name: row.model_id,
      complete: row.complete,
      fragmented: row.fragmented,
      missing: row.missing,
    }));
  }, [state]);

  return (
    <Stack spacing={2.2}>
      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Stack spacing={1.5}>
          <Typography variant="h5">Leaderboard (live pipeline)</Typography>
          <Typography color="text.secondary">
            Leaderboard pipeline starts automatically on app startup and computes gene-level + BUSCO metrics for every .gff file.
          </Typography>
          <Typography sx={{ alignSelf: "flex-start" }}>
            {state?.stage ? `Stage: ${state.stage}` : "Stage: idle"}
            {state?.current_model ? ` • Current: ${state.current_model}` : ""}
          </Typography>
          <LinearProgress variant="determinate" value={progress} />
          <Typography variant="body2" color="text.secondary">
            {state?.completed_models || 0}/{state?.total_models || 0} completed • {progress}%
          </Typography>
          {state?.message ? <Alert severity="info">{state.message}</Alert> : null}
          {state?.error ? <Alert severity="error">{state.error}</Alert> : null}
        </Stack>
      </Paper>

      <Paper className="glass-card" sx={{ p: 2.4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Gene-level bar chart</Typography>
        <Box sx={{ width: "100%", height: 340 }}>
          <ResponsiveContainer>
            <BarChart data={geneChartData} margin={{ top: 10, right: 10, bottom: 40, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-20} textAnchor="end" interval={0} height={72} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="mrna_cds" stackId="gene" fill="#0ea5e9" name="CDS mRNA" />
              <Bar dataKey="mrna_exon" stackId="gene" fill="#22c55e" name="exon mRNA" />
              <Bar dataKey="lncrna_exon" stackId="gene" fill="#0f766e" name="exon lncRNA" />
            </BarChart>
          </ResponsiveContainer>
        </Box>
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
        <Typography variant="h6" sx={{ mb: 1 }}>BUSCO bar chart</Typography>
        <Box sx={{ width: "100%", height: 340 }}>
          <ResponsiveContainer>
            <BarChart data={buscoChartData} margin={{ top: 10, right: 10, bottom: 40, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-20} textAnchor="end" interval={0} height={72} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="complete" stackId="busco" fill="#16a34a" name="Complete" />
              <Bar dataKey="fragmented" stackId="busco" fill="#f59e0b" name="Fragmented" />
              <Bar dataKey="missing" stackId="busco" fill="#ef4444" name="Missing" />
            </BarChart>
          </ResponsiveContainer>
        </Box>
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
