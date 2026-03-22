import { createTheme } from "@mui/material/styles";

export function buildTheme() {
  return createTheme({
    palette: {
      mode: "light",
      primary: { main: "#0f766e" },
      secondary: { main: "#0ea5e9" },
      success: { main: "#16a34a" },
      warning: { main: "#f59e0b" },
      error: { main: "#ef4444" },
      info: { main: "#0284c7" },
      background: {
        default: "#f3fbf8",
        paper: "rgba(255,255,255,0.84)"
      },
      text: {
        primary: "#0b1f1a",
        secondary: "rgba(11,31,26,0.72)"
      },
      divider: "rgba(15,118,110,0.18)"
    },
    shape: {
      borderRadius: 18
    },
    typography: {
      fontFamily:
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      h3: { fontWeight: 850, letterSpacing: -0.6 },
      h4: { fontWeight: 820, letterSpacing: -0.4 },
      h5: { fontWeight: 760 },
      h6: { fontWeight: 740 },
      button: { textTransform: "none", fontWeight: 760 }
    },
    components: {
      MuiAppBar: {
        styleOverrides: {
          root: {
            color: "#0b1f1a",
            background: "rgba(255,255,255,0.72)",
            backdropFilter: "blur(12px)",
            borderBottom: "1px solid rgba(15,118,110,0.14)",
            boxShadow: "none"
          }
        }
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            border: "1px solid rgba(15,118,110,0.14)",
            boxShadow: "0 10px 30px rgba(2, 44, 34, 0.08)"
          }
        }
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 14
          }
        }
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 12
          }
        }
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            background: "rgba(255,255,255,0.66)",
            backdropFilter: "blur(10px)"
          }
        }
      }
    }
  });
}
