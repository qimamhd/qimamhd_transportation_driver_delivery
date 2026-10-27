odoo.define('qimamhd_transportation_driver_delivery.trip_sheet_viewer', function (require) {
    'use strict';
    var $ = require('jquery');
    function viewer(el) {
        var $v = $(el), img = $v.find('.qimam-trip-image')[0];
        if (!img || $v.data('trip-ready')) return;
        $v.data('trip-ready', true);
        var stage = $v.find('.qimam-trip-stage')[0];
        var state = {zoom: 1, angle: 0, x: 0, y: 0}, drag = null;
        function render() {
            img.style.transform = 'translate(' + state.x + 'px,' + state.y + 'px) rotate(' + state.angle + 'deg) scale(' + state.zoom + ')';
            $v.find('.qimam-trip-percent').text(Math.round(state.zoom * 100) + '%');
            stage.style.cursor = state.zoom > 1 ? 'grab' : 'default';
        }
        function zoom(v) { state.zoom = Math.max(0.25, Math.min(5, v)); render(); }
        $v.on('click', '[data-trip-action]', function (e) {
            e.preventDefault(); e.stopPropagation();
            var action = $(this).attr('data-trip-action');
            if (action === 'left') state.angle -= 90;
            if (action === 'right') state.angle += 90;
            if (action === 'in') zoom(state.zoom + 0.25);
            if (action === 'out') zoom(state.zoom - 0.25);
            if (action === 'fit' || action === 'reset') { state.zoom = 1; state.x = 0; state.y = 0; if (action === 'reset') state.angle = 0; }
            if (action === 'fullscreen') {
                if (document.fullscreenElement === $v[0] && document.exitFullscreen) document.exitFullscreen();
                else if ($v[0].requestFullscreen) $v[0].requestFullscreen();
            }
            render();
        });
        stage.addEventListener('wheel', function(e) {
            if (!e.ctrlKey) return;
            e.preventDefault(); zoom(state.zoom + (e.deltaY < 0 ? 0.1 : -0.1));
        }, {passive:false});
        stage.addEventListener('pointerdown', function(e) {
            if (state.zoom <= 1) return;
            drag = {id:e.pointerId, px:e.clientX, py:e.clientY, x:state.x, y:state.y};
            if (stage.setPointerCapture) stage.setPointerCapture(e.pointerId);
        });
        stage.addEventListener('pointermove', function(e) {
            if (!drag || drag.id !== e.pointerId) return;
            state.x = drag.x + e.clientX - drag.px; state.y = drag.y + e.clientY - drag.py; render();
        });
        ['pointerup','pointercancel','lostpointercapture'].forEach(function(name) {
            stage.addEventListener(name, function(){drag = null;});
        });
        render();
    }
    // Odoo 13's HTML field may render after the modal is mounted.
    var observer = new MutationObserver(function() {
        document.querySelectorAll('.qimam-trip-viewer').forEach(viewer);
    });
    $(function() {
        document.querySelectorAll('.qimam-trip-viewer').forEach(viewer);
        observer.observe(document.body, {childList:true, subtree:true});
    });
});
