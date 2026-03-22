import React, { useMemo, useRef, useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  FormControlLabel,
  FormGroup,
  Grid,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Toolbar,
  Typography,
} from "@mui/material";
import ScienceIcon from "@mui/icons-material/Science";
import CalculateIcon from "@mui/icons-material/Calculate";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import CodeIcon from "@mui/icons-material/Code";
import BiotechIcon from "@mui/icons-material/Biotech";

const PYTHON_PREDS_PLACEHOLDER = `[
  [
    [0, 0],
    [1, 0],
    [1, 1],
    [0, 0],
    [1, 1],
    [1, 1],
    [0, 0],
    [0, 0]
  ],
  [
    [0, 0],
    [1, 0],
    [1, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [1, 0],
    [1, 0],
    [0, 0],
    [0, 0]
  ]
]`;

const PYTHON_TARGETS_PLACEHOLDER = `[
  [
    [0, 0],
    [1, 0],
    [1, 1],
    [0, 0],
    [1, 1],
    [1, 1],
    [0, 0],
    [0, 0]
  ],
  [
    [0, 0],
    [1, 0],
    [1, 0],
    [1, 0],
    [0, 0],
    [0, 0],
    [1, 0],
    [1, 0],
    [0, 0],
    [0, 0]
  ]
]`;

const MAPPING_PLACEHOLDER = `TX0001|GENE0001|mRNA|+|GRCh38|chr1|1-8
TX0002|GENE0002|lnc_RNA|-|GRCh38|chr5|1-10`;

const PYTHON_API_SNIPPET = `import evaluate

metric = evaluate.load("shmelev/gene-level-metric")

result = metric.compute(
    preds=[
        [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
            [1, 1],
            [1, 1],
            [0, 0],
            [0, 0],
        ]
    ],
    targets=[
        [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
            [1, 1],
            [1, 1],
            [0, 0],
            [0, 0],
        ]
    ],
    mapping=[
        "TX0001|GENE0001|mRNA|+|GRCh38|chr1|1-8",
    ],
    stratifier="type",
    types=["mRNA", "lnc_RNA"],
    segments=["exon", "CDS"],
)

print(result)`;

const GFF_API_SNIPPET = `import evaluate

metric = evaluate.load("shmelev/gene-level-metric")

result = metric.compute(
    pred_gff="predictions.gff",
    true_gff="reference.gff",
    stratifier="type",
    types=["mRNA", "lnc_RNA"],
    segments=["exon", "CDS"],
)

print(result)`;

const STRATIFIERS = [
  { value: "type", label: "type / transcript_type" },
  { value: "transcript", label: "transcript / transcript_id" },
  { value: "gene", label: "gene / gene_id" },
  { value: "chromosome", label: "chromosome" },
  { value: "strand", label: "strand" },
];

const TYPE_OPTIONS = [
  { value: "mRNA", label: "mRNA" },
  { value: "lnc_RNA", label: "lnc_RNA" },
];

const SEGMENT_OPTIONS = [
  { value: "exon", label: "exon" },
  { value: "CDS", label: "CDS" },
];

const EMPTY_PYTHON_FORM = {
  predsText: "",
  targetsText: "",
  mappingText: "",
  stratifier: "type",
  types: ["mRNA", "lnc_RNA"],
  segments: ["exon", "CDS"],
};

const EMPTY_GFF_FORM = {
  stratifier: "type",
  types: ["mRNA", "lnc_RNA"],
  segments: ["exon", "CDS"],
  predFile: null,
  trueFile: null,
  predFileName: "",
  trueFileName: "",
};

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function mappingToText(mapping) {
  return Array.isArray(mapping) ? mapping.join("\n") : "";
}

function parseJsonText(text, label) {
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON array.`);
  }
  return parsed;
}

function parseMapping(text) {
  const trimmed = text.trim();
  if (!trimmed) {
    return [];
  }

  if (trimmed.startsWith("[")) {
    const parsed = parseJsonText(trimmed, "mapping");
    if (parsed.some((item) => typeof item !== "string")) {
      throw new Error("mapping JSON must be an array of strings.");
    }
    return parsed;
  }

  return trimmed
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function segmentListToString(segments) {
  if (!segments || segments.length === 0) {
    return "—";
  }
  return segments.map(([start, end]) => `[${start}, ${end})`).join(", ");
}

function CodePanel({ children }) {
  return (
    <Box component="pre" className="code-panel mono">
      {children}
    </Box>
  );
}

function SegmentScrollBox({ segments }) {
  const value = segmentListToString(segments);
  return (
    <Box className="segment-scrollbox mono" title={value}>
      {value}
    </Box>
  );
}

function MatchChip({ value }) {
  if (value === null || value === undefined) {
    return <Chip size="small" label="n/a" variant="outlined" />;
  }
  if (value) {
    return <Chip size="small" label="match" color="success" />;
  }
  return <Chip size="small" label="mismatch" color="error" />;
}

function SectionTitle({ icon = null, title, subtitle }) {
  return (
    <Stack spacing={1.1}>
      <Stack direction="row" alignItems="center" spacing={1}>
        {icon ? icon : null}
        <Typography variant="h5">{title}</Typography>
      </Stack>
      {subtitle ? (
        <Typography color="text.secondary">{subtitle}</Typography>
      ) : null}
    </Stack>
  );
}

function SummaryCard({ label, value }) {
  return (
    <Box className="summary-chip-box">
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" sx={{ mt: 0.5 }}>
        {value}
      </Typography>
    </Box>
  );
}

function DetailTable({ details, segments }) {
  if (!details || details.length === 0) {
    return (
      <Alert severity="info">
        No transcript rows are available for the current filters.
      </Alert>
    );
  }

  return (
    <Box className="result-table-wrap">
      <Table className="metric-table">
        <TableHead>
          <TableRow>
            <TableCell>Transcript</TableCell>
            <TableCell>Gene</TableCell>
            <TableCell>Type / strand</TableCell>
            <TableCell>Coordinate / length</TableCell>
            {segments.map((segment) => (
              <React.Fragment key={segment}>
                <TableCell className="segment-column">{segment} predicted</TableCell>
                <TableCell className="segment-column">{segment} target</TableCell>
                <TableCell>{segment} match</TableCell>
              </React.Fragment>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {details.map((row) => (
            <TableRow key={`${row.transcript_id}-${row.gene_id}`}>
              <TableCell>
                <Typography fontWeight={760}>{row.transcript_id}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {row.seqid}
                </Typography>
              </TableCell>
              <TableCell>{row.gene_id}</TableCell>
              <TableCell>{`${row.transcript_type} / ${row.strand}`}</TableCell>
              <TableCell>
                <Typography>{row.coord}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {row.length} nt
                </Typography>
              </TableCell>
              {segments.map((segment) => (
                <React.Fragment key={`${row.transcript_id}-${segment}`}>
                  <TableCell>
                    <SegmentScrollBox segments={row.segments?.[segment]?.predicted || []} />
                  </TableCell>
                  <TableCell>
                    <SegmentScrollBox segments={row.segments?.[segment]?.target || []} />
                  </TableCell>
                  <TableCell>
                    <MatchChip value={row.segments?.[segment]?.match} />
                  </TableCell>
                </React.Fragment>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

export default function App() {
  const [tab, setTab] = useState("python");
  const [pythonForm, setPythonForm] = useState(EMPTY_PYTHON_FORM);
  const [gffForm, setGffForm] = useState(EMPTY_GFF_FORM);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const predFileInputRef = useRef(null);
  const trueFileInputRef = useRef(null);

  const segmentTotals = useMemo(() => {
    return result?.totals_by_segment || {};
  }, [result]);

  const setPythonField = (key) => (event) => {
    setPythonForm((current) => ({ ...current, [key]: event.target.value }));
  };

  const setGffField = (key) => (event) => {
    setGffForm((current) => ({ ...current, [key]: event.target.value }));
  };

  const clearGffInputs = () => {
    if (predFileInputRef.current) {
      predFileInputRef.current.value = "";
    }
    if (trueFileInputRef.current) {
      trueFileInputRef.current.value = "";
    }
  };

  const toggleArrayValue = (scope, key, value) => (event) => {
    const checked = event.target.checked;
    if (scope === "python") {
      setPythonForm((current) => ({
        ...current,
        [key]: checked
          ? [...current[key], value]
          : current[key].filter((item) => item !== value),
      }));
    } else {
      setGffForm((current) => ({
        ...current,
        [key]: checked
          ? [...current[key], value]
          : current[key].filter((item) => item !== value),
      }));
    }
  };

  const handleFilePick = (key) => (event) => {
    const file = event.target.files?.[0] || null;
    setGffForm((current) => ({
      ...current,
      [key]: file,
      [`${key}Name`]: file?.name || "",
    }));
  };

  const fillPythonExample = async () => {
    setError("");
    try {
      const response = await fetch("/api/example/python");
      const payload = await response.json();
      setTab("python");
      setPythonForm({
        predsText: prettyJson(payload.preds),
        targetsText: prettyJson(payload.targets),
        mappingText: mappingToText(payload.mapping),
        stratifier: payload.stratifier,
        types: payload.types,
        segments: payload.segments,
      });
      setResult(null);
    } catch {
      setError("Could not load the built-in example.");
    }
  };

  const clearAll = () => {
    setResult(null);
    setError("");
    setPythonForm(EMPTY_PYTHON_FORM);
    setGffForm(EMPTY_GFF_FORM);
    clearGffInputs();
  };

  const computePython = async () => {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const preds = parseJsonText(pythonForm.predsText, "preds");
      const targets = parseJsonText(pythonForm.targetsText, "targets");
      const mapping = parseMapping(pythonForm.mappingText);

      const response = await fetch("/api/compute/python", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          preds,
          targets,
          mapping,
          stratifier: pythonForm.stratifier,
          types: pythonForm.types,
          segments: pythonForm.segments,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Computation failed.");
      }

      setResult(payload);
    } catch (err) {
      setError(err.message || "Computation failed.");
    } finally {
      setLoading(false);
    }
  };

  const computeGff = async () => {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      if (!gffForm.predFile || !gffForm.trueFile) {
        throw new Error("Please choose both prediction and reference GFF files.");
      }

      const pred_gff_text = await gffForm.predFile.text();
      const true_gff_text = await gffForm.trueFile.text();

      const response = await fetch("/api/compute/gff", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          pred_gff_text,
          true_gff_text,
          stratifier: gffForm.stratifier,
          types: gffForm.types,
          segments: gffForm.segments,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Computation failed.");
      }

      setResult(payload);
      setGffForm((current) => ({
        ...current,
        predFile: null,
        trueFile: null,
        predFileName: "",
        trueFileName: "",
      }));
      clearGffInputs();
    } catch (err) {
      setError(err.message || "Computation failed.");
    } finally {
      setLoading(false);
    }
  };

  const activeSegments = result?.segments || (tab === "python" ? pythonForm.segments : gffForm.segments);

  return (
    <Box>
      <AppBar position="sticky">
        <Toolbar>
          <Typography variant="h6">Gene-level Metric</Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={3.2}>
          <Paper className="glass-card hero-card" sx={{ p: { xs: 2.4, md: 3.4 } }}>
            <Stack spacing={2.2}>
              <Stack
                direction={{ xs: "column", md: "row" }}
                justifyContent="space-between"
                alignItems={{ xs: "flex-start", md: "flex-start" }}
                spacing={2}
              >
                <Box sx={{ maxWidth: 860 }}>
                  <Typography variant="h3" sx={{ mb: 1 }}>
                    Gene-level exon–intron metric
                  </Typography>
                  <Typography variant="h6" color="text.secondary" sx={{ maxWidth: 840 }}>
                    Implementation of a metric for biologically rigorous evaluation of exon–intron structure.
                  </Typography>
                </Box>
              </Stack>

              <Stack direction="row" spacing={1} className="badge-row">
                <Box className="label-badge label-badge--metric">
                  <ScienceIcon fontSize="small" />
                  Metric playground
                </Box>
                <Box className="label-badge label-badge--hf">
                  <span style={{ fontSize: "1.05rem" }}>🤗</span>
                  Hugging Face API
                </Box>
              </Stack>
            </Stack>
          </Paper>

          <Box className="top-two-column-grid">
            <Paper className="glass-card" sx={{ p: { xs: 2.2, md: 3 } }}>
              <Stack spacing={2.4}>
                <SectionTitle
                  icon={<CodeIcon color="primary" />}
                  title="How to use this metric with Evaluate"
                  subtitle="Both the Python-like matrix mode and the GFF mode can be loaded through the same Hugging Face metric."
                />
                <Grid container spacing={2}>
                  <Grid item xs={12} xl={6}>
                    <Typography variant="subtitle1" sx={{ mb: 1 }}>
                      Python-like mode
                    </Typography>
                    <CodePanel>{PYTHON_API_SNIPPET}</CodePanel>
                  </Grid>
                  <Grid item xs={12} xl={6}>
                    <Typography variant="subtitle1" sx={{ mb: 1 }}>
                      GFF mode
                    </Typography>
                    <CodePanel>{GFF_API_SNIPPET}</CodePanel>
                  </Grid>
                </Grid>
              </Stack>
            </Paper>

            <Paper className="glass-card metric-description" sx={{ p: { xs: 2.2, md: 3 } }}>
              <Stack spacing={1.6}>
                <SectionTitle title="How the metric is computed" />
                <Typography color="text.secondary">
                  The metric compares exact interval reconstruction, not per-base overlap. For every
                  transcript, contiguous runs of ones are converted into half-open segments such as
                  <span className="mono"> [1, 3)</span>. A segment is counted as correct only when the
                  predicted segment set and the target segment set are exactly equal for the selected
                  segment type.
                </Typography>
                <Typography color="text.secondary">
                  Two input modes are supported. In Python-like mode, each transcript is represented by
                  a binary matrix with shape <span className="mono">(transcript length, number of segments)</span>.
                  Each column corresponds to one selected segment from the
                  <span className="mono"> segments </span> argument. In GFF mode, the metric extracts
                  exon and CDS intervals from the uploaded annotations and performs the same exact-set comparison.
                </Typography>
                <Typography color="text.secondary">
                  The output is grouped by the selected <span className="mono">stratifier</span>. This
                  means you can count exact matches per transcript type, transcript id, gene id,
                  chromosome, or strand. The implementation accepts the aliases
                  <span className="mono"> type / transcript_type</span>,
                  <span className="mono"> transcript / transcript_id</span>, and
                  <span className="mono"> gene / gene_id</span>.
                </Typography>
              </Stack>
            </Paper>
          </Box>

          <Paper className="glass-card section-anchor" sx={{ p: { xs: 2.2, md: 3 } }}>
            <Stack spacing={2.2}>
              <SectionTitle
                title="Accepted input format"
                subtitle="These requirements are static and always apply."
              />

              <Divider />

              <Grid container spacing={3}>
                <Grid item xs={12} xl={6}>
                  <Typography variant="h6" sx={{ mb: 1.2 }}>
                    Python-like mode
                  </Typography>
                  <Stack spacing={1.1}>
                    <Typography color="text.secondary">
                      <span className="mono">preds</span> and <span className="mono">targets</span> must be lists of
                      transcript arrays. Each transcript array must be binary and 2D:
                      <span className="mono"> (transcript_length, number_of_selected_segments)</span>.
                    </Typography>
                    <Typography color="text.secondary">
                      The selected segments define the column order. For example, with
                      <span className="mono"> segments=["exon", "CDS"] </span>
                      column 0 is exon and column 1 is CDS.
                    </Typography>
                    <Typography color="text.secondary">
                      Each mapping row must have seven fields:
                      <span className="mono"> transcript_id|gene_id|transcript_type|strand|genome|chrom|coord</span>.
                    </Typography>
                    <Typography color="text.secondary">
                      Allowed transcript types:
                      <span className="mono"> mRNA</span> and <span className="mono">lnc_RNA</span>.
                      Allowed segments:
                      <span className="mono"> exon</span> and <span className="mono">CDS</span>.
                    </Typography>
                  </Stack>
                  <Box sx={{ mt: 1.4 }}>
                    <CodePanel>{`preds = [
  [
    [0, 0],
    [1, 0],
    [1, 1],
    [0, 0]
  ]
]

mapping = [
  "TX0001|GENE0001|mRNA|+|GRCh38|chr1|1-4"
]`}</CodePanel>
                  </Box>
                </Grid>

                <Grid item xs={12} xl={6}>
                  <Typography variant="h6" sx={{ mb: 1.2 }}>
                    GFF mode
                  </Typography>
                  <Stack spacing={1.1}>
                    <Typography color="text.secondary">
                      The reference GFF must contain gene rows with <span className="mono">ID</span>,
                      transcript rows of type <span className="mono">mRNA</span> and/or
                      <span className="mono"> lnc_RNA</span> with
                      <span className="mono"> ID</span> and <span className="mono">Parent</span>,
                      and exon/CDS rows with <span className="mono">Parent=&lt;transcript_id&gt;</span>.
                    </Typography>
                    <Typography color="text.secondary">
                      In this implementation, the prediction GFF uses
                      <span className="mono"> seqid = transcript_id</span>, and exon/CDS coordinates are
                      interpreted in transcript-relative coordinates.
                    </Typography>
                    <Typography color="text.secondary">
                      Only the selected transcript types and segment types are scored. The same
                      <span className="mono"> stratifier</span>, <span className="mono">types</span>, and
                      <span className="mono"> segments</span> arguments are shared with Python-like mode.
                    </Typography>
                  </Stack>
                </Grid>
              </Grid>
            </Stack>
          </Paper>

          <Paper className="glass-card" sx={{ p: { xs: 2.2, md: 3 } }}>
            <Stack spacing={2.4}>
              <SectionTitle
                icon={<CalculateIcon color="primary" />}
                title="Playground"
                subtitle="Choose the input mode, provide the required fields, and run the metric."
              />

              <Tabs
                value={tab}
                onChange={(_, value) => {
                  setTab(value);
                  setResult(null);
                  setError("");
                }}
              >
                <Tab value="python" label="Python-like input" />
                <Tab value="gff" label="GFF input" />
              </Tabs>

              {tab === "python" ? (
                <Stack spacing={2.2}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" sx={{ mb: 0.8 }}>
                        Stratifier
                      </Typography>
                      <Select fullWidth value={pythonForm.stratifier} onChange={setPythonField("stratifier")}>
                        {STRATIFIERS.map((item) => (
                          <MenuItem key={item.value} value={item.value}>
                            {item.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" sx={{ mb: 0.8 }}>
                        Transcript types
                      </Typography>
                      <FormGroup row>
                        {TYPE_OPTIONS.map((option) => (
                          <FormControlLabel
                            key={option.value}
                            control={
                              <Switch
                                checked={pythonForm.types.includes(option.value)}
                                onChange={toggleArrayValue("python", "types", option.value)}
                              />
                            }
                            label={option.label}
                          />
                        ))}
                      </FormGroup>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" sx={{ mb: 0.8 }}>
                        Segments
                      </Typography>
                      <FormGroup row>
                        {SEGMENT_OPTIONS.map((option) => (
                          <FormControlLabel
                            key={option.value}
                            control={
                              <Switch
                                checked={pythonForm.segments.includes(option.value)}
                                onChange={toggleArrayValue("python", "segments", option.value)}
                              />
                            }
                            label={option.label}
                          />
                        ))}
                      </FormGroup>
                    </Grid>
                  </Grid>

                  <Grid container spacing={2}>
                    <Grid item xs={12} xl={6}>
                      <TextField
                        label="preds"
                        fullWidth
                        multiline
                        minRows={14}
                        className="codeish"
                        placeholder={PYTHON_PREDS_PLACEHOLDER}
                        value={pythonForm.predsText}
                        onChange={setPythonField("predsText")}
                      />
                    </Grid>
                    <Grid item xs={12} xl={6}>
                      <TextField
                        label="targets"
                        fullWidth
                        multiline
                        minRows={14}
                        className="codeish"
                        placeholder={PYTHON_TARGETS_PLACEHOLDER}
                        value={pythonForm.targetsText}
                        onChange={setPythonField("targetsText")}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        label="mapping"
                        fullWidth
                        multiline
                        minRows={4}
                        className="codeish"
                        placeholder={MAPPING_PLACEHOLDER}
                        value={pythonForm.mappingText}
                        onChange={setPythonField("mappingText")}
                      />
                    </Grid>
                  </Grid>

                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.2}>
                    <Button variant="contained" startIcon={<CalculateIcon />} onClick={computePython} disabled={loading}>
                      Compute metric
                    </Button>
                    <Button variant="outlined" startIcon={<ScienceIcon />} onClick={fillPythonExample} disabled={loading}>
                      Paste example
                    </Button>
                    <Button variant="outlined" startIcon={<DeleteSweepIcon />} onClick={clearAll} disabled={loading}>
                      Clear all
                    </Button>
                  </Stack>
                </Stack>
              ) : (
                <Stack spacing={2.2}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" sx={{ mb: 0.8 }}>
                        Stratifier
                      </Typography>
                      <Select fullWidth value={gffForm.stratifier} onChange={setGffField("stratifier")}>
                        {STRATIFIERS.map((item) => (
                          <MenuItem key={item.value} value={item.value}>
                            {item.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" sx={{ mb: 0.8 }}>
                        Transcript types
                      </Typography>
                      <FormGroup row>
                        {TYPE_OPTIONS.map((option) => (
                          <FormControlLabel
                            key={option.value}
                            control={
                              <Switch
                                checked={gffForm.types.includes(option.value)}
                                onChange={toggleArrayValue("gff", "types", option.value)}
                              />
                            }
                            label={option.label}
                          />
                        ))}
                      </FormGroup>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" sx={{ mb: 0.8 }}>
                        Segments
                      </Typography>
                      <FormGroup row>
                        {SEGMENT_OPTIONS.map((option) => (
                          <FormControlLabel
                            key={option.value}
                            control={
                              <Switch
                                checked={gffForm.segments.includes(option.value)}
                                onChange={toggleArrayValue("gff", "segments", option.value)}
                              />
                            }
                            label={option.label}
                          />
                        ))}
                      </FormGroup>
                    </Grid>
                  </Grid>

                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Button component="label" fullWidth variant="outlined" startIcon={<UploadFileIcon />}>
                        {gffForm.predFileName || "Choose prediction GFF"}
                        <input ref={predFileInputRef} hidden type="file" accept=".gff,.gff3,.txt" onChange={handleFilePick("predFile")} />
                      </Button>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Button component="label" fullWidth variant="outlined" startIcon={<UploadFileIcon />}>
                        {gffForm.trueFileName || "Choose reference GFF"}
                        <input ref={trueFileInputRef} hidden type="file" accept=".gff,.gff3,.txt" onChange={handleFilePick("trueFile")} />
                      </Button>
                    </Grid>
                  </Grid>

                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.2}>
                    <Button variant="contained" startIcon={<CalculateIcon />} onClick={computeGff} disabled={loading}>
                      Compute metric
                    </Button>
                    <Button variant="outlined" startIcon={<DeleteSweepIcon />} onClick={clearAll} disabled={loading}>
                      Clear all
                    </Button>
                  </Stack>
                </Stack>
              )}

              {loading ? (
                <Stack direction="row" spacing={1.2} alignItems="center">
                  <CircularProgress size={22} />
                  <Typography>Computing the metric…</Typography>
                </Stack>
              ) : null}

              {error ? <Alert severity="error">{error}</Alert> : null}
            </Stack>
          </Paper>

          {result ? (
            <>
              <Paper className="glass-card" sx={{ p: { xs: 2.2, md: 3 } }}>
                <Stack spacing={2.2}>
                  <SectionTitle
                    icon={<BiotechIcon color="primary" />}
                    title="Metric result"
                    subtitle={`Mode: ${result.mode}. Stratifier: ${result.stratifier}.`}
                  />

                  <Box className="summary-grid">
                    <SummaryCard label="Categories" value={result.n_categories} />
                    <SummaryCard label="Transcripts inspected" value={result.n_transcripts} />
                    {Object.entries(segmentTotals).map(([segment, value]) => (
                      <SummaryCard key={segment} label={`Total ${segment} matches`} value={value} />
                    ))}
                  </Box>

                  <TableContainer>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Category</TableCell>
                          {result.segments.map((segment) => (
                            <TableCell key={segment}>{segment}</TableCell>
                          ))}
                          <TableCell>Total</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {result.rows.map((row) => (
                          <TableRow key={row.category}>
                            <TableCell>{row.category}</TableCell>
                            {result.segments.map((segment) => (
                              <TableCell key={`${row.category}-${segment}`}>{row.values[segment]}</TableCell>
                            ))}
                            <TableCell>{row.total}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>

                  <Typography variant="subtitle1">Raw result</Typography>
                  <CodePanel>{prettyJson(result.raw_result)}</CodePanel>
                </Stack>
              </Paper>

              <Paper className="glass-card" sx={{ p: { xs: 2.2, md: 3 } }}>
                <Stack spacing={2.2}>
                  <SectionTitle
                    icon={<BiotechIcon color="primary" />}
                    title="Per-transcript details"
                    subtitle="Segment lists are shown inside horizontally scrollable cells so long interval sets do not break the layout."
                  />
                  <DetailTable details={result.details} segments={activeSegments} />
                </Stack>
              </Paper>
            </>
          ) : null}
        </Stack>
      </Container>
    </Box>
  );
}
