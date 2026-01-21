//! UI rendering with ratatui.

use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::Paragraph,
    Frame,
};

use crate::app::App;

const PRIMARY_COLOR: Color = Color::Cyan;

pub fn render_ui(frame: &mut Frame, app: &App) {
    let area = frame.area();

    // Compact layout with fixed-height visualization above track info
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),  // Header
            Constraint::Length(1),  // Spacer
            Constraint::Length(7),  // Visualization (fixed height)
            Constraint::Length(1),  // Spacer
            Constraint::Length(1),  // Track Info
            Constraint::Length(1),  // Controls
            Constraint::Length(1),  // Attribution
        ])
        .split(area);

    render_header(frame, chunks[0], app);
    render_visualization(frame, chunks[2], app);
    render_track_info(frame, chunks[4], app);

    if app.is_selecting_preset() {
        render_preset_selection(frame, chunks[5], app);
    } else {
        render_controls(frame, chunks[5], app);
    }

    render_attribution(frame, chunks[6]);
}

fn render_header(frame: &mut Frame, area: Rect, app: &App) {
    let mut spans = vec![
        Span::styled("  Fomu", Style::default().fg(Color::White).add_modifier(Modifier::BOLD)),
        Span::styled(
            format!("  [{}]", app.preset().name),
            Style::default().fg(PRIMARY_COLOR),
        ),
    ];

    if let Some(pending) = app.pending_preset() {
        let progress = app.download_progress();
        if progress.progress > 0.0 && !progress.completed {
            spans.push(Span::styled(
                format!("  → [{}] {}%", pending, (progress.progress * 100.0) as u32),
                Style::default().fg(Color::Yellow),
            ));
        } else {
            spans.push(Span::styled(
                format!("  → [{}] downloading...", pending),
                Style::default().fg(Color::Yellow),
            ));
        }
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn render_visualization(frame: &mut Frame, area: Rect, app: &App) {
    // Use actual terminal area dimensions for responsive visualization
    let width = area.width as usize;
    let height = area.height as usize;

    let lines = app.visualizer().render_sized(app.rms(), app.bands(), width, height);
    let viz_lines: Vec<Line> = lines
        .iter()
        .map(|s| Line::from(Span::styled(s.clone(), Style::default().fg(PRIMARY_COLOR))))
        .collect();
    frame.render_widget(Paragraph::new(viz_lines), area);
}

fn render_track_info(frame: &mut Frame, area: Rect, app: &App) {
    let status_icon = if app.is_playing() { "▶" } else { "⏸" };
    let track_name = app.current_track().map(|t| t.name).unwrap_or("Loading...");

    let spans = vec![
        Span::styled(format!("  {} ", status_icon), Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(track_name, Style::default().fg(Color::White)),
        Span::styled(" — Scott Buckley", Style::default().fg(Color::DarkGray)),
        Span::styled(format!("  {}", app.elapsed_time()), Style::default().fg(Color::DarkGray)),
    ];

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn render_controls(frame: &mut Frame, area: Rect, app: &App) {
    let volume_pct = (app.volume() * 100.0) as u32;

    let spans = vec![
        Span::styled(format!("  Vol: {}%", volume_pct), Style::default().fg(PRIMARY_COLOR)),
        Span::styled("  │  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[space]", Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(" pause  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[+/-]", Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(" vol  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[n]", Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(" skip  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[p]", Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(" preset  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[q]", Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(" quit", Style::default().fg(Color::DarkGray)),
    ];

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn render_preset_selection(frame: &mut Frame, area: Rect, app: &App) {
    let mut spans = vec![Span::styled(
        "  Select preset: ",
        Style::default().add_modifier(Modifier::BOLD),
    )];

    for (i, preset) in app.all_presets().iter().enumerate() {
        if i > 0 {
            spans.push(Span::styled(" ", Style::default().fg(Color::DarkGray)));
        }

        let has_tracks = app.preset_has_tracks(preset);

        if i == app.selected_preset_index() {
            spans.push(Span::styled(
                format!("[{}]", preset.name),
                Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD | Modifier::REVERSED),
            ));
        } else if has_tracks {
            spans.push(Span::styled(preset.name, Style::default().fg(Color::White)));
        } else {
            spans.push(Span::styled(
                preset.name,
                Style::default().fg(Color::DarkGray).add_modifier(Modifier::ITALIC),
            ));
        }
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn render_attribution(frame: &mut Frame, area: Rect) {
    let spans = vec![
        Span::styled("  Music by Scott Buckley (CC-BY 4.0) — support him at ", Style::default().fg(Color::DarkGray)),
        Span::styled("scottbuckley.com.au", Style::default().fg(Color::DarkGray).add_modifier(Modifier::UNDERLINED)),
    ];

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}
