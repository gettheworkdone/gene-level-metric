import React, { useMemo, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  FormControlLabel,
  Grid,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import ScienceIcon from "@mui/icons-material/Science";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import CalculateIcon from "@mui/icons-material/Calculate";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import TuneIcon from "@mui/icons-material/Tune";
import BiotechIcon from "@mui/icons-material/Biotech";

const PREDS_PLACEHOLDER = `[
  [0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0],
  [0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0]
]`;

const TARGETS_PLACEHOLDER = `[
  [0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0],
  [0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0]
]`;

const MAPPING_PLACEHOLDER = `chr1|mRNA|GENE0001|TX0001|+|1-12
chr1|lncRNA|GENE0002|TX0002|+|1-12`;

const DNA_PLACEHOLDER = `[
  "ATGCGTAACTGA",
  "TTACTGACCTGA"
]`;

const DEFAULT_DSS = "GT, GC, AT";
const DEFAULT_ASS = "AG, AC, TG";

const EMPTY_FORM = {
  predsText: "",
  targetsText: "",
  mappingText: "",
  dnaText: "",
  cdsHeuristics: false,
  spliceFilter: false,
  dssText: DEFAULT_DSS,
  assText: DEFAULT_ASS,
};

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function mappingToText(mapping) {
  return Array.isArray(mapping) ? mapping.join("\n") : "";
}

function dnaToText(value) {
  if (Array.isArray(value)) {
    return prettyJson(value);
  }
  return value || "";
}

function parseJsonArray(text, label) {
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }

  if (!Array.isArray(parsed) || parsed.some((row) => !Array.isArray(row))) {
    throw new Error(`${label} must be a JSON array of arrays.`);
  }

  return parsed;
}

function parseMapping(text) {
  const trimmed = text.trim();
  if (!trimmed) {
    return [];
  }

  if (trimmed.startsWith("[")) {
    let parsed;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      throw new Error("Mapping must be either newline-separated text or a JSON array of strings.");
    }

    if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) {
      throw new Error("Mapping JSON must be an array of strings.");
    }

    return parsed;
  }

  return trimmed
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseDna(text) {
  const trimmed = text.trim();
  if (!trimmed) {
    return "";
  }

  if (trimmed.startsWith("[")) {
    let parsed;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      throw new Error("DNA sequences must be a raw string, newline-separated strings, or a JSON array of strings.");
    }

    if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) {
      throw new Error("DNA JSON must be an array of strings.");
    }

    return parsed.map((item) => item.replace(/\s+/g, "").toUpperCase());
  }

  const lines = trimmed
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/\s+/g, "").toUpperCase());

  if (lines.length === 1) {
    return lines[0];
  }

  return lines;
}

function parseMotifs(text, fallback) {
  const items = text
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);

  return items.length ? items : fallback;
}

function segmentListToString(segments) {
  if (!segments || segments.length === 0) {
    return "—";
  }
  return segments.map(([start, end]) => `[${start}, ${end})`).join(", ");
}

function ParameterChip({ label, active }) {
  return (
    <Chip
      label={`${label}: ${active ? "on" : "off"}`}
      color={active ? "primary" : "default"}
      variant={active ? "filled" : "outlined"}
      size="small"
    />
  );
}

export default function App() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const scoreLabel = useMemo(() => {
    if (!result) {
      return "—";
    }
    return `${(result.score * 100).toFixed(2)}%`;
  }, [result]);

  const setField = (key) => (event) => {
    const value = event?.target?.type === "checkbox" ? event.target.checked : event.target.value;
    setForm((current) => ({ ...current, [key]: value }));
  };

  const fillFromExample = async (kind) => {
    setError("");
    try {
      const response = await fetch("/api/example");
      const data = await response.json();
      const example = data[kind];
      if (!example) {
        throw new Error("Example preset was not found.");
      }

      setForm({
        predsText: prettyJson(example.preds),
        targetsText: prettyJson(example.targets),
        mappingText: mappingToText(example.mapping),
        dnaText: dnaToText(example.dna_sequences),
        cdsHeuristics: example.cds_heuristics,
        spliceFilter: example.splice_filter,
        dssText: (example.dss || []).join(", "),
        assText: (example.ass || []).join(", "),
      });
      setResult(null);
    } catch (err) {
      setError(err.message || "Failed to load example.");
    }
  };

  const clearAll = () => {
    setForm(EMPTY_FORM);
    setResult(null);
    setError("");
  };

  const computeMetric = async () => {
    setError("");
    setLoading(true);
    setResult(null);

    try {
      const payload = {
        preds: parseJsonArray(form.predsText, "Predictions"),
        targets: parseJsonArray(form.targetsText, "Targets"),
        mapping: parseMapping(form.mappingText),
        dna_sequences: parseDna(form.dnaText),
        cds_heuristics: form.cdsHeuristics,
        splice_filter: form.spliceFilter,
        dss: parseMotifs(form.dssText, ["GT", "GC", "AT"]),
        ass: parseMotifs(form.assText, ["AG", "AC", "TG"]),
      };

      const response = await fetch("/api/compute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Metric computation failed.");
      }

      setResult(data);
    } catch (err) {
      setError(err.message || "Metric computation failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box minHeight="100vh">
      <AppBar position="sticky" elevation={0} color="transparent">
        <Toolbar>
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ flexGrow: 1 }}>
            <ScienceIcon color="primary" />
            <Box>
              <Typography variant="h6" sx={{ lineHeight: 1.1 }}>
                GENATATOR Gene-level Metric
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Exact transcript agreement with optional splice filtering and CDS heuristics
              </Typography>
            </Box>
          </Stack>
          <Tooltip title="This app is built as a Docker Space with a React frontend and FastAPI backend.">
            <Chip label="Single-page playground" color="primary" variant="outlined" />
          </Tooltip>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Paper className="glass-card hero-card" sx={{ p: { xs: 3, md: 4 }, mb: 3 }}>
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} md={8}>
              <Stack spacing={2}>
                <Chip label="Metric playground" color="success" sx={{ alignSelf: "flex-start" }} />
                <Typography variant="h3">Compute the GENATATOR gene-level score in the browser.</Typography>
                <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 860 }}>
                  Paste prediction masks, target masks, mapping rows, optional DNA sequence input,
                  switch heuristics on or off, and get an exact gene-level score with per-transcript
                  details.
                </Typography>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1.2} flexWrap="wrap">
                  <ParameterChip label="splice filter" active={form.spliceFilter} />
                  <ParameterChip label="CDS heuristics" active={form.cdsHeuristics} />
                  <Chip label={`donors: ${form.dssText || DEFAULT_DSS}`} variant="outlined" size="small" />
                  <Chip label={`acceptors: ${form.assText || DEFAULT_ASS}`} variant="outlined" size="small" />
                </Stack>
              </Stack>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper className="glass-card" sx={{ p: 3 }}>
                <Stack spacing={1}>
                  <Typography variant="overline" color="text.secondary">
                    Current score
                  </Typography>
                  <Typography className="metric-value">{scoreLabel}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {result
                      ? `${result.matched_genes} matched transcript${
                          result.matched_genes === 1 ? "" : "s"
                        } out of ${result.total_genes}.`
                      : "Run the metric to see the exact match rate."}
                  </Typography>
                </Stack>
              </Paper>
            </Grid>
          </Grid>
        </Paper>

        <Grid container spacing={3}>
          <Grid item xs={12} lg={7}>
            <Paper className="glass-card" sx={{ p: 3 }}>
              <Stack spacing={2.25}>
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  spacing={1.2}
                  justifyContent="space-between"
                  alignItems={{ xs: "stretch", sm: "center" }}
                >
                  <Box>
                    <Typography variant="h5">Playground</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Paste JSON masks and mapping rows, then compute the metric.
                    </Typography>
                  </Box>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                    <Button
                      variant="outlined"
                      startIcon={<AutoFixHighIcon />}
                      onClick={() => fillFromExample("simple")}
                    >
                      Load simple example
                    </Button>
                    <Button
                      variant="outlined"
                      color="secondary"
                      startIcon={<BiotechIcon />}
                      onClick={() => fillFromExample("heuristic")}
                    >
                      Load CDS / splice example
                    </Button>
                  </Stack>
                </Stack>

                {error && <Alert severity="error">{error}</Alert>}

                <Alert severity="info">
                  Mapping can be newline-separated or a JSON string array. DNA input can be empty, a
                  single sequence applied to all rows, multiple newline-separated sequences, or a JSON
                  string array.
                </Alert>

                <TextField
                  className="codeish"
                  label="Predictions"
                  placeholder={PREDS_PLACEHOLDER}
                  value={form.predsText}
                  onChange={setField("predsText")}
                  multiline
                  minRows={7}
                  fullWidth
                  helperText="JSON array of arrays with 0/1 values."
                />

                <TextField
                  className="codeish"
                  label="Targets"
                  placeholder={TARGETS_PLACEHOLDER}
                  value={form.targetsText}
                  onChange={setField("targetsText")}
                  multiline
                  minRows={7}
                  fullWidth
                  helperText="JSON array of arrays with 0/1 values."
                />

                <TextField
                  className="codeish"
                  label="Mapping"
                  placeholder={MAPPING_PLACEHOLDER}
                  value={form.mappingText}
                  onChange={setField("mappingText")}
                  multiline
                  minRows={4}
                  fullWidth
                  helperText="Format: chrom|gene_type|gene_id|transcript_id|strand|coord"
                />

                <TextField
                  className="codeish"
                  label="DNA sequence(s)"
                  placeholder={DNA_PLACEHOLDER}
                  value={form.dnaText}
                  onChange={setField("dnaText")}
                  multiline
                  minRows={4}
                  fullWidth
                  helperText="Optional unless splice filter or CDS heuristics is enabled."
                />

                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Donor splice motifs"
                      value={form.dssText}
                      onChange={setField("dssText")}
                      fullWidth
                      helperText="Comma-separated. Example: GT, GC, AT"
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Acceptor splice motifs"
                      value={form.assText}
                      onChange={setField("assText")}
                      fullWidth
                      helperText="Comma-separated. Example: AG, AC, TG"
                    />
                  </Grid>
                </Grid>

                <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                  <FormControlLabel
                    control={<Switch checked={form.spliceFilter} onChange={setField("spliceFilter")} />}
                    label="Enable splice filter"
                  />
                  <FormControlLabel
                    control={
                      <Switch checked={form.cdsHeuristics} onChange={setField("cdsHeuristics")} />
                    }
                    label="Enable CDS heuristics"
                  />
                </Stack>

                <Stack direction={{ xs: "column", sm: "row" }} spacing={1.2}>
                  <Button
                    variant="contained"
                    size="large"
                    startIcon={loading ? <CircularProgress size={18} color="inherit" /> : <CalculateIcon />}
                    onClick={computeMetric}
                    disabled={loading}
                  >
                    {loading ? "Computing..." : "Compute metric"}
                  </Button>
                  <Button
                    variant="outlined"
                    size="large"
                    color="inherit"
                    startIcon={<DeleteSweepIcon />}
                    onClick={clearAll}
                  >
                    Clear all
                  </Button>
                </Stack>
              </Stack>
            </Paper>
          </Grid>

          <Grid item xs={12} lg={5}>
            <Stack spacing={3}>
              <Paper className="glass-card" sx={{ p: 3 }}>
                <Stack spacing={1.2}>
                  <Typography variant="h5">How the score is computed</Typography>
                  <Typography variant="body2" color="text.secondary">
                    The metric extracts contiguous 1-segments from each prediction and target row.
                    After optional filtering and CDS conversion, a transcript is counted as correct
                    only when the final predicted segments match the target segments exactly.
                  </Typography>
                  <Divider sx={{ my: 1 }} />
                  <Stack spacing={1}>
                    <Chip label="Exact set equality after all enabled transforms" sx={{ width: "fit-content" }} />
                    <Chip
                      label="First and last exons are always kept in splice filtering"
                      variant="outlined"
                      sx={{ width: "fit-content" }}
                    />
                    <Chip
                      label="CDS heuristics search for the longest ORF with M...*"
                      variant="outlined"
                      sx={{ width: "fit-content" }}
                    />
                  </Stack>
                </Stack>
              </Paper>

              <Paper className="glass-card" sx={{ p: 3 }}>
                <Stack spacing={1.2}>
                  <Typography variant="h5">Input checklist</Typography>
                  <Typography variant="body2" color="text.secondary">
                    The API validates lengths, binary values, mapping format, strand values, and DNA
                    length consistency before computing the score.
                  </Typography>
                  <Stack spacing={1}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <CheckCircleOutlineIcon color="success" fontSize="small" />
                      <Typography variant="body2">Predictions and targets must have the same number of rows.</Typography>
                    </Stack>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <CheckCircleOutlineIcon color="success" fontSize="small" />
                      <Typography variant="body2">Each row must contain only 0 and 1 values.</Typography>
                    </Stack>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <CheckCircleOutlineIcon color="success" fontSize="small" />
                      <Typography variant="body2">Each mapping row must contain exactly 6 pipe-separated fields.</Typography>
                    </Stack>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <CheckCircleOutlineIcon color="success" fontSize="small" />
                      <Typography variant="body2">DNA is required only when splice filtering or CDS heuristics is enabled.</Typography>
                    </Stack>
                  </Stack>
                </Stack>
              </Paper>

              <Accordion className="glass-card" defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <TuneIcon color="primary" />
                    <Typography variant="h6">Accepted input formats</Typography>
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={2}>
                    <Box>
                      <Typography variant="subtitle2">Predictions / targets</Typography>
                      <Typography variant="body2" color="text.secondary" className="mono">
                        JSON array of arrays, for example [[0,1,1,0],[1,1,0,0]]
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="subtitle2">Mapping</Typography>
                      <Typography variant="body2" color="text.secondary" className="mono">
                        Either one row per line or a JSON array of strings.
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="subtitle2">DNA sequence(s)</Typography>
                      <Typography variant="body2" color="text.secondary" className="mono">
                        Empty, one raw sequence for all rows, newline-separated sequences, or a JSON
                        array of strings.
                      </Typography>
                    </Box>
                  </Stack>
                </AccordionDetails>
              </Accordion>
            </Stack>
          </Grid>
        </Grid>

        {result && (
          <Stack spacing={3} sx={{ mt: 3 }}>
            <Paper className="glass-card" sx={{ p: 3 }}>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Typography variant="overline" color="text.secondary">
                    Gene-level score
                  </Typography>
                  <Typography className="metric-value">{scoreLabel}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="overline" color="text.secondary">
                    Matched transcripts
                  </Typography>
                  <Typography variant="h4">{result.matched_genes}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="overline" color="text.secondary">
                    Total transcripts
                  </Typography>
                  <Typography variant="h4">{result.total_genes}</Typography>
                </Grid>
              </Grid>
            </Paper>

            <Paper className="glass-card" sx={{ p: 3 }}>
              <Stack spacing={2}>
                <Typography variant="h5">Per-transcript details</Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Transcript</TableCell>
                        <TableCell>Gene</TableCell>
                        <TableCell>Type / strand</TableCell>
                        <TableCell>Raw predicted segments</TableCell>
                        <TableCell>Final predicted segments</TableCell>
                        <TableCell>Target segments</TableCell>
                        <TableCell align="center">Match</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {result.details.map((row) => (
                        <TableRow key={`${row.index}-${row.transcript_id}`} hover>
                          <TableCell>
                            <Stack spacing={0.35}>
                              <Typography variant="body2" fontWeight={700}>
                                {row.transcript_id}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {row.chrom}:{row.coord}
                              </Typography>
                            </Stack>
                          </TableCell>
                          <TableCell>{row.gene_id}</TableCell>
                          <TableCell>{`${row.gene_type} / ${row.strand}`}</TableCell>
                          <TableCell className="mono">{segmentListToString(row.raw_pred_segments)}</TableCell>
                          <TableCell className="mono">{segmentListToString(row.final_pred_segments)}</TableCell>
                          <TableCell className="mono">{segmentListToString(row.target_segments)}</TableCell>
                          <TableCell align="center">
                            <Chip
                              label={row.match ? "match" : "mismatch"}
                              color={row.match ? "success" : "error"}
                              size="small"
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Stack>
            </Paper>

            <Accordion className="glass-card">
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="h6">Raw API output</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <TextField
                  className="codeish"
                  value={prettyJson(result)}
                  multiline
                  minRows={12}
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
              </AccordionDetails>
            </Accordion>
          </Stack>
        )}

        <Box sx={{ py: 3 }}>
          <Typography variant="body2" color="text.secondary" align="center">
            Styled to visually match the green/teal bio-themed GENATATOR leaderboard aesthetic,
            while focusing on a single interactive metric page.
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}
