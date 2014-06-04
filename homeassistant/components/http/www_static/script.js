// from http://stackoverflow.com/questions/1403888/get-escaped-url-parameter
function getURLParameter(name) {
    return decodeURI(
        (RegExp(name + '=' + '(.+?)(&|$)').exec(location.search)||[,null])[1]
    );
}


$(function() {
    $("[data-service]").click(function() {
        var form = $(".form-call-service");

        var el = $(this);
        var parts = el.attr("data-service").split("/");

        form.find("#domain").val(parts[0]);
        form.find("#service").val(parts[1]);

        var entity_id = el.attr("data-entity_id");

        if(entity_id) {
            form.find("#service_data").val(JSON.stringify({entity_id: entity_id}));
        } else {
            form.find("#service_data").val("");
        }

        if(el.attr("data-service-autofire")) {
            form.submit();
        }

        return false;
    }).css('cursor', 'pointer')
})