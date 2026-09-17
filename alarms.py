# 4. Графіки
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("### Середня тривалість тривог за роками")
    avg_duration_yr = df_alerts[df_alerts['year'] >= 2022].groupby('year')['duration_minutes'].mean().round(1).reset_index()
    
    fig_bar = px.bar(avg_duration_yr, x='year', y='duration_minutes', text='duration_minutes')
    fig_bar.update_traces(marker_color='#3b82f6', marker_line_width=0, textposition='outside', textfont_color='#ffffff')
    fig_bar.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#ffffff', # ТУТ: змінив на білий
        xaxis=dict(showgrid=False, title="Рік", tickfont=dict(color='#ffffff')), 
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Тривалість (хв)", tickfont=dict(color='#ffffff')),
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_chart2:
    st.markdown("### Розподіл рекордних днів (Топ 5%)")
    daily_alerts = df_alerts.groupby('date').agg(
        alert_count=('uid', 'count'),
        total_duration=('duration_minutes', 'sum')
    ).reset_index()

    total_alert_days = len(daily_alerts)
    top_n = max(int(total_alert_days * 0.05), 10)

    set_longest = set(daily_alerts.nlargest(top_n, 'total_duration')['date'])
    set_most = set(daily_alerts.nlargest(top_n, 'alert_count')['date'])
    days_both = set_longest.intersection(set_most)
    
    sizes = [
        len(set_longest - days_both),
        len(set_most - days_both),
        len(days_both),
        total_alert_days - len(set_longest.union(set_most))
    ]
    labels = ['Найдовші (Топ 5%)', 'Найбільше (Топ 5%)', 'Обидві категорії', 'Інші дні']
    colors = ['#ef4444', '#f59e0b', '#10b981', '#374151']

    fig_pie = go.Figure(data=[go.Pie(labels=labels, values=sizes, hole=.7, marker_colors=colors, textfont=dict(color='#ffffff'))])
    fig_pie.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#ffffff', # ТУТ: змінив на білий
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=-0.2, 
            xanchor="center", 
            x=0.5,
            font=dict(color='#ffffff') # Легенда тепер теж біла
        )
    )
    st.plotly_chart(fig_pie, use_container_width=True)
